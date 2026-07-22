# Urban Energy Insights

Urban Energy Insights is an event-driven platform for ingesting building energy telemetry, generating anomaly insights, and exposing those insights through a clean API.  
Its primary value is fast operational visibility: raw meter data is converted into actionable "what changed and why" signals with deterministic, testable business rules.

## Project Overview

This system tracks energy usage per building and flags unusual behavior patterns such as demand spikes and off-hours overconsumption.

Key capabilities:
- Building registry management
- CSV telemetry ingestion with duplicate protection
- Stream-based processing (Redis Streams + worker)
- Insight generation using baseline + recent-history rule evaluation
- Insight lifecycle management (`open`, `ack`, `resolved`)

## System Architecture

The system is split into three runtime services plus one data layer:

1. **API service (FastAPI + SQLAlchemy)**
   - Handles write/read APIs for buildings, ingestion, and insights.
   - Parses and validates CSV input.
   - Persists readings and emits ingestion events to Redis Streams.
   - Hosts internal processing endpoint used by worker.

2. **Worker service (Python + Redis consumer group)**
   - Consumes `energy_events` stream with at-least-once semantics.
   - Calls API internal processing endpoint for each event.
   - ACKs only successful events, leaving failed events pending for retry/visibility.

3. **Redis**
   - Durable event queue (stream) between ingestion and analytics processing.

4. **PostgreSQL**
   - Stores buildings, readings, baselines, and insights.

### Domain Flow

1. Client uploads CSV for a building.
2. API validates and stores unique readings.
3. API emits one stream event per inserted reading.
4. Worker consumes event and triggers analytics processing.
5. API computes updated slot baseline + rule checks.
6. API stores generated insights and exposes them through query endpoints.

## Data Model

- `buildings`: building metadata and timezone
- `energy_readings`: time-series usage points (`building_id`, `ts`, `kwh`) with uniqueness guard
- `baselines`: expected energy profile by `dow/hour` per building
- `insights`: generated anomalies with category, severity, explanation, and status

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- GNU Make (optional, for convenience commands)

## Local Setup

1. Clone repository and move into project root.
2. Start services:
   ```bash
   make up
   ```
3. Run DB migrations (in a second terminal):
   ```bash
   make migrate
   ```
4. API will be available at:
   - `http://localhost:8000`
   - OpenAPI docs: `http://localhost:8000/docs`

### Local Environment Variables

Defined via `docker-compose.yml` for local development:
- `DATABASE_URL=postgresql+psycopg://uei:uei@postgres:5432/uei`
- `REDIS_URL=redis://redis:6379/0`
- `INTERNAL_API_TOKEN=local-dev-token`
- `API_BASE_URL=http://api:8000` (worker)

## API Usage

### Health
```http
GET /health
```

### Buildings
```http
POST /buildings
Content-Type: application/json

{
  "id": "b1",
  "name": "HQ Tower",
  "type": "office",
  "timezone": "UTC"
}
```

```http
GET /buildings
GET /buildings/{building_id}
```

### Ingestion
```http
POST /ingest/csv?building_id=b1
Content-Type: multipart/form-data
file=<csv file containing timestamp,kwh columns>
```

Response shape:
```json
{
  "inserted": 10,
  "duplicates": 2,
  "published_events": 10,
  "publish_failures": 0
}
```

### Insights
```http
GET /buildings/{building_id}/insights?status=open&limit=100
GET /insights?limit=100
```

```http
PATCH /insights/{insight_id}
Content-Type: application/json

{
  "status": "ack"
}
```

### Internal Processing Endpoint

Used by worker, not external clients:
```http
POST /internal/process-event
x-internal-token: local-dev-token
Content-Type: application/json

{
  "building_id": "b1",
  "timestamp": "2026-02-01T00:00:00+00:00"
}
```

## Testing

Run API tests:
```bash
make test-api
```

Covered critical paths:
- building creation + duplicate conflict behavior
- CSV ingestion validation and duplicate skip logic
- event processing flow producing at least one spike insight

## Security and Hardening Notes

Implemented:
- strict schema validation (timezone, statuses, input limits)
- internal endpoint token gate (`INTERNAL_API_TOKEN`)
- duplicate-reading protection with DB-level unique constraint
- explicit malformed-event handling in worker
- bounded pagination limits to prevent unbounded queries

Recommended next hardening:
- rotate internal token via secrets manager
- add API authn/authz for external endpoints
- add rate limiting and request correlation IDs

## Performance Notes

Implemented:
- removed per-row commits in ingestion path (single transaction with savepoints)
- event-driven decoupling to keep ingestion latency low
- selective querying windows in insight processing

Recommended next optimization:
- partition `energy_readings` by time for large tenants
- add indexes for high-cardinality read paths (`building_id`, `created_at`, `status`)
- evaluate batched event payloads for high-throughput ingestion

## Future Roadmap (Enterprise Scale)

### AWS Deployment Strategy
- **Compute**: ECS Fargate or EKS for API and worker autoscaling.
- **Database**: Amazon RDS PostgreSQL with read replicas and automated backups.
- **Streaming**: Redis OSS on ElastiCache or move to Kinesis/Kafka for higher scale.
- **Networking**: private subnets + ALB + WAF; least-privilege IAM roles.

### CI/CD Strategy
- GitHub Actions pipeline:
  1. Lint + tests + security scans (SAST/dependency scanning)
  2. Build/version Docker images
  3. Push to ECR
  4. Deploy to staging then production with manual approval gates
- Add Alembic migration checks and smoke tests post-deploy.

### Product/Architecture Evolution
- rule-engine abstraction for configurable anomaly strategies
- tenant isolation model (multi-tenant RBAC and per-tenant quotas)
- real-time notifications (webhooks, Slack, PagerDuty)
- observability stack (OpenTelemetry traces + metrics dashboards + alerting)
