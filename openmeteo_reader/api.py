"""
FastAPI web interface for the weather data
"""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from openmeteo_reader.domain.models import HOME_TIMEZONE
from openmeteo_reader.ports.weather_query_repository import WeatherQueryRepository

# Global repository instances, set by main.py at startup - mirrors sdm-modbus-reader's
# api.py wiring, since this is a separate process/composition root from the importer.
_repository: WeatherQueryRepository | None = None
_forecast_repository: WeatherQueryRepository | None = None


def set_repository(repository: WeatherQueryRepository | None) -> None:
    """Set the actuals repository instance to use"""
    global _repository
    _repository = repository


def set_forecast_repository(repository: WeatherQueryRepository | None) -> None:
    """Set the forecast repository instance to use"""
    global _forecast_repository
    _forecast_repository = repository


app = FastAPI(title="Home Weather")

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/current")
async def get_current():
    """The most recently stored reading"""
    if _repository is None:
        raise HTTPException(status_code=503, detail="Repository not initialized")

    reading = _repository.latest()
    if reading is None:
        raise HTTPException(status_code=404, detail="No data stored yet")

    return {"timestamp": reading.timestamp.isoformat(), "values": reading.values}


@app.get("/api/series")
async def get_series(variable: str, hours: int = 72):
    """A single variable's values for the last `hours` hours"""
    if _repository is None:
        raise HTTPException(status_code=503, detail="Repository not initialized")

    since = datetime.now(tz=UTC) - timedelta(hours=hours)
    points = _repository.series(variable, since)
    return [{"time": time.isoformat(), "value": value} for time, value in points]


def local_midnight_today() -> datetime:
    """The start of today in Home's local time - where a forecast day begins"""
    return datetime.now(HOME_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)


@app.get("/api/forecast/series")
async def get_forecast_series(variable: str, days: int = 8):
    """A variable's min/median/max ensemble spread for the next `days` days"""
    if _forecast_repository is None:
        raise HTTPException(status_code=503, detail="Forecast repository not initialized")

    since = local_midnight_today()
    until = since + timedelta(days=days)

    stats = {}
    for stat in ("min", "median", "max"):
        stats[stat] = dict(_forecast_repository.series(f"{variable}_{stat}", since, until))

    times = sorted(set(stats["min"]) | set(stats["median"]) | set(stats["max"]))
    return [
        {
            "time": time.isoformat(),
            "min": stats["min"].get(time),
            "median": stats["median"].get(time),
            "max": stats["max"].get(time),
        }
        for time in times
    ]


@app.get("/api/forecast/daily-precipitation")
async def get_daily_precipitation(days: int = 8):
    """
    One entry per local day: the day's expected rain total (min/median/max across
    the pooled ensemble) and the chance, in percent, of at least 1 mm.

    The running total resets at local midnight, so the day's last hour holds the
    day's total.
    """
    if _forecast_repository is None:
        raise HTTPException(status_code=503, detail="Forecast repository not initialized")

    since = local_midnight_today()
    until = since + timedelta(days=days)
    fields = {
        "min": "precipitation_total_min",
        "median": "precipitation_total_median",
        "max": "precipitation_total_max",
        "probability": "precipitation_total_probability",
    }

    days_out: dict[str, dict] = {}
    for key, field in fields.items():
        for time, value in sorted(_forecast_repository.series(field, since, until)):
            day = time.astimezone(HOME_TIMEZONE).date().isoformat()
            days_out.setdefault(day, {"date": day})[key] = value
    return [days_out[day] for day in sorted(days_out)]


@app.get("/")
async def index(request: Request):
    """Serve the forecast page - the live/default view"""
    return templates.TemplateResponse(request, "index.html")


@app.get("/history")
async def history(request: Request):
    """Serve the actuals logbook - a reference view, not the live default"""
    return templates.TemplateResponse(request, "history.html")
