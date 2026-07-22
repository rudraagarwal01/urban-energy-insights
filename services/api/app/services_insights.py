from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.models import Baseline, Building, EnergyReading, Insight

RECENT_WINDOW_DAYS = 30
MIN_BASELINE_POINTS = 3
MIN_SPIKE_HISTORY_POINTS = 6


@dataclass(frozen=True)
class RuleResult:
    category: str
    severity: float
    explanation: str


def _upsert_baseline(
    db: Session,
    building_id: str,
    timestamp: datetime,
    readings: list[EnergyReading],
) -> Baseline | None:
    dow = timestamp.weekday()
    hour = timestamp.hour
    slot_values = [r.kwh for r in readings if r.ts.weekday() == dow and r.ts.hour == hour]
    if len(slot_values) < MIN_BASELINE_POINTS:
        return None

    expected = mean(slot_values)
    std = pstdev(slot_values) if len(slot_values) > 1 else 0.0
    baseline = db.get(Baseline, {"building_id": building_id, "dow": dow, "hour": hour})
    if baseline is None:
        baseline = Baseline(
            building_id=building_id,
            dow=dow,
            hour=hour,
            expected_kwh=expected,
            std_kwh=std,
        )
        db.add(baseline)
    else:
        baseline.expected_kwh = expected
        baseline.std_kwh = std
    return baseline


def _evaluate_rules(
    current: EnergyReading,
    recent_readings: list[EnergyReading],
    baseline: Baseline | None,
) -> list[RuleResult]:
    results: list[RuleResult] = []

    history = [r.kwh for r in recent_readings if r.ts < current.ts]
    if len(history) >= MIN_SPIKE_HISTORY_POINTS:
        avg = mean(history)
        std = pstdev(history) if len(history) > 1 else 0.0
        spike_threshold = avg + max(2.5 * std, avg * 0.4)
        if current.kwh > spike_threshold:
            severity = max((current.kwh - avg) / max(avg, 0.01), 0.1)
            results.append(
                RuleResult(
                    category="spike",
                    severity=severity,
                    explanation=f"Consumption spiked to {current.kwh:.2f} kWh against recent average {avg:.2f} kWh.",
                )
            )

    if baseline:
        baseline_threshold = baseline.expected_kwh + max(2 * baseline.std_kwh, baseline.expected_kwh * 0.25)
        if current.kwh > baseline_threshold:
            severity = max((current.kwh - baseline.expected_kwh) / max(baseline.expected_kwh, 0.01), 0.1)
            category = "off_hours_usage" if current.ts.hour < 6 or current.ts.hour >= 22 else "abnormal_usage"
            results.append(
                RuleResult(
                    category=category,
                    severity=severity,
                    explanation=(
                        f"Observed {current.kwh:.2f} kWh vs slot baseline "
                        f"{baseline.expected_kwh:.2f} kWh (std {baseline.std_kwh:.2f})."
                    ),
                )
            )

    return results


def process_energy_event(db: Session, building_id: str, timestamp: datetime) -> int:
    building = db.get(Building, building_id)
    if building is None:
        raise LookupError("Building not found")

    current = db.execute(
        select(EnergyReading)
        .where(and_(EnergyReading.building_id == building_id, EnergyReading.ts == timestamp))
        .limit(1)
    ).scalar_one_or_none()
    if current is None:
        return 0

    from_ts = timestamp - timedelta(days=RECENT_WINDOW_DAYS)
    recent_readings = (
        db.execute(
            select(EnergyReading)
            .where(
                and_(
                    EnergyReading.building_id == building_id,
                    EnergyReading.ts >= from_ts,
                    EnergyReading.ts <= timestamp,
                )
            )
            .order_by(desc(EnergyReading.ts))
            .limit(6000)
        )
        .scalars()
        .all()
    )
    baseline = _upsert_baseline(db, building_id, timestamp, recent_readings)
    findings = _evaluate_rules(current, recent_readings, baseline)

    created = 0
    for finding in findings:
        existing = db.execute(
            select(Insight).where(
                and_(
                    Insight.building_id == building_id,
                    Insight.start_ts == timestamp,
                    Insight.end_ts == timestamp,
                    Insight.category == finding.category,
                    Insight.status == "open",
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            Insight(
                building_id=building_id,
                start_ts=timestamp,
                end_ts=timestamp,
                category=finding.category,
                severity=finding.severity,
                explanation=finding.explanation,
                status="open",
            )
        )
        created += 1

    db.commit()
    return created
