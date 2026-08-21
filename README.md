# openmeteo-reader

Fetches weather data for home from Open-Meteo and stores it in InfluxDB, with a small
website: a live forecast (today + 7 days, with ensemble uncertainty bands) at `/`, and
an actuals logbook (2019&rarr;now) at `/history`.

Three data sources are used, for different purposes:

- **Forecast API** (`past_hours`) - the rolling recent window of *actuals*. Its values
  are model analysis and revise for up to ~3 hours after the fact as observations land,
  so every hourly run re-fetches and overwrites a trailing buffer, not just the newest
  hour.
- **Historical Weather API** (ERA5 reanalysis) - one-off backfill of actuals for
  anything older than the Forecast API's rolling window covers.
- **Ensemble API** (DWD ICON, `icon_seamless`) - the forward-looking forecast, today
  through +7 days. 40 model members per variable are collapsed into min/median/max
  before storage, not kept raw - the app only needs the spread, not per-member
  analysis. Covers temperature and precipitation only.

See `../CONTEXT.md` ("Weather domain") for the location, buckets, and schema.

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

# Refresh the ensemble forecast (run hourly)
uv run python -m openmeteo_reader forecast

# Serve the website + JSON API
uv run python -m openmeteo_reader serve
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|--------------|
| `INFLUX_URL` | Yes | - | InfluxDB URL |
| `INFLUX_TOKEN` | Yes | - | InfluxDB authentication token |
| `INFLUX_ORG` | Yes | - | InfluxDB organization |
| `INFLUX_BUCKET` | No | `weather` | Actuals bucket name |
| `INFLUX_FORECAST_BUCKET` | No | `forecast` | Forecast bucket name |
| `HOME_LATITUDE` | No | 50.99528169318774 | Only relevant to `main`/`backfill`/`forecast` |
| `HOME_LONGITUDE` | No | 3.2131169748116113 | Only relevant to `main`/`backfill`/`forecast` |
| `FORECAST_HORIZON_DAYS` | No | `8` | Only relevant to `forecast` |
| `HOST` / `PORT` | No | `0.0.0.0` / `8000` | Only relevant to `serve` |

Copy `.env.example` to `.env` and fill in your InfluxDB token/org before deploying.

## InfluxDB schema

**Actuals** - bucket `weather` (configurable via `INFLUX_BUCKET`), measurement
`openmeteo`, tag `location=home`. Fields are whatever Open-Meteo returned for that
hour - the Forecast and Historical APIs don't share an identical variable set
(different soil-depth bands, wind-height levels), so older backfilled years and the
live rolling window may have slightly different field names for those niche
variables. Every field is written as a float, even when Open-Meteo returns it as a
JSON integer (humidity, cloud cover, weather codes) - InfluxDB rejects a field
written with an inconsistent type across points.

**Forecast** - bucket `forecast` (configurable via `INFLUX_FORECAST_BUCKET`), same
measurement/tag. Fields are `<variable>_min`, `<variable>_median`, `<variable>_max`
for `temperature_2m`, `precipitation`, and `wind_speed_10m` - the ensemble spread,
not raw member values. `precipitation` additionally gets `precipitation_total_min/
median/max`: each member's own running total for the UTC day, reduced to
min/median/max, used for the day's expected precipitation total. Summing the
hourly `precipitation_median` values instead would misstate it - see the comment
on `CUMULATIVE_VARIABLES` in `domain/ensemble_response.py`. Points are future-dated
and get fully overwritten on every `forecast` run (models update; they don't
accumulate like actuals).

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
