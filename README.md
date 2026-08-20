# openmeteo-reader

Fetches hourly weather data for home from Open-Meteo and stores it in InfluxDB, with a
small website to view current conditions and recent history.

Two data sources are used, for different purposes:

- **Forecast API** (`past_hours`) - the rolling recent window. Its values are model
  analysis and revise for up to ~3 hours after the fact as observations land, so every
  hourly run re-fetches and overwrites a trailing buffer, not just the newest hour.
- **Historical Weather API** (ERA5 reanalysis) - one-off backfill for anything older
  than the Forecast API's rolling window covers.

See `../CONTEXT.md` ("Weather domain") for the location, bucket, and schema.

## Architecture

Hexagonal: `domain/` has no infrastructure dependencies; `ports/` define the
interfaces `application/` depends on; `adapters/` implement them against Open-Meteo,
InfluxDB, and FastAPI. `bootstrap.py` is the composition root for the importer;
`api.py` is a separate composition root for the website (own process, own container).

Two containers, matching `entsoe-influx`'s deployment shape:

- **importer** (`Dockerfile`) - a batch job (`main` / `backfill` commands), triggered
  hourly by an `ofelia` sidecar in `docker-compose.yml`.
- **api** (`Dockerfile.api`) - the FastAPI website + JSON API, served continuously via
  the CLI's `serve` command (not uvicorn directly - `serve` is what wires the
  InfluxDB-backed repository into the app before it starts).

## Development

```bash
uv sync
uv run pytest -v
uv run ruff check .
```

## CLI

```bash
# Fetch and store the rolling recent window (run hourly)
uv run python -m openmeteo_reader main

# One-off historical backfill
uv run python -m openmeteo_reader backfill --start 2019-01-01

# Serve the website + JSON API
uv run python -m openmeteo_reader serve
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|--------------|
| `INFLUX_URL` | Yes | - | InfluxDB URL |
| `INFLUX_TOKEN` | Yes | - | InfluxDB authentication token |
| `INFLUX_ORG` | Yes | - | InfluxDB organization |
| `INFLUX_BUCKET` | No | `weather` | InfluxDB bucket name |
| `HOME_LATITUDE` | No | 50.99528169318774 | Only relevant to `main`/`backfill` |
| `HOME_LONGITUDE` | No | 3.2131169748116113 | Only relevant to `main`/`backfill` |
| `HOST` / `PORT` | No | `0.0.0.0` / `8000` | Only relevant to `serve` |

Copy `.env.example` to `.env` and fill in your InfluxDB token/org before deploying.

## InfluxDB schema

- Bucket: `weather` (configurable via `INFLUX_BUCKET`)
- Measurement: `openmeteo`
- Tag: `location=home`
- Fields: whatever Open-Meteo returned for that hour - the Forecast and Historical
  APIs don't share an identical variable set (different soil-depth bands, wind-height
  levels), so older backfilled years and the live rolling window may have slightly
  different field names for those niche variables. Every field is written as a float,
  even when Open-Meteo returns it as a JSON integer (humidity, cloud cover, weather
  codes) - InfluxDB rejects a field written with an inconsistent type across points.

## Deployment (Core node, `.5`)

```bash
cp .env.example .env   # fill in INFLUX_TOKEN, INFLUX_ORG
docker compose up -d
```

This starts the website (routed via Traefik at `weather.victoor.io`, DNS already
points there) and an `ofelia` scheduler that runs the importer every hour. Both join
the `jelle_default` docker network - same one InfluxDB and Traefik are on - so
`INFLUX_URL` defaults to the internal `http://influxdb:8086` and the Traefik labels
match the other `*.victoor.io` services (`entrypoints=websecure`,
`tls.certresolver=cloudflare`).

The `openmeteo-reader-api`/`-scheduler` images need to be pullable from GHCR without
auth on `.5` - either make the GHCR packages public, or `docker login ghcr.io` there
with a PAT that has `read:packages`.

To backfill history once, run the importer image directly:

```bash
docker run --rm --env-file .env ghcr.io/jellevictoor/openmeteo-reader:latest \
  backfill --start 2019-01-01
```
