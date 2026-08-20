"""
FastAPI web interface for the weather data
"""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from openmeteo_reader.ports.weather_query_repository import WeatherQueryRepository

# Global repository instance, set by main.py at startup - mirrors sdm-modbus-reader's
# api.py wiring, since this is a separate process/composition root from the importer.
_repository: WeatherQueryRepository | None = None


def set_repository(repository: WeatherQueryRepository | None) -> None:
    """Set the repository instance to use"""
    global _repository
    _repository = repository


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


@app.get("/")
async def index(request: Request):
    """Serve the main HTML page"""
    return templates.TemplateResponse(request, "index.html")
