from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base

class Building(Base):
    __tablename__ = "buildings"

    id = Column(String, primary_key=True)  # e.g., "b1"
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    readings = relationship("EnergyReading", back_populates="building")


class EnergyReading(Base):
    __tablename__ = "energy_readings"
    __table_args__ = (
        UniqueConstraint("building_id", "ts", name="uq_building_ts"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    building_id = Column(String, ForeignKey("buildings.id"), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    kwh = Column(Float, nullable=False)
    source = Column(String, nullable=True, default="csv")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    building = relationship("Building", back_populates="readings")


class Baseline(Base):
    __tablename__ = "baselines"

    building_id = Column(String, ForeignKey("buildings.id"), primary_key=True)
    dow = Column(Integer, primary_key=True)   # 0-6
    hour = Column(Integer, primary_key=True)  # 0-23
    expected_kwh = Column(Float, nullable=False)
    std_kwh = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    building_id = Column(String, ForeignKey("buildings.id"), nullable=False)
    start_ts = Column(DateTime(timezone=True), nullable=False)
    end_ts = Column(DateTime(timezone=True), nullable=False)
    category = Column(String, nullable=False)   # overnight/weekend/etc
    severity = Column(Float, nullable=False)
    explanation = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")  # open/ack/resolved
    created_at = Column(DateTime(timezone=True), server_default=func.now())
