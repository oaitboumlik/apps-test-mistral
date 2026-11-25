"""Current weather from the Open-Meteo API: the open, key-free weather source."""

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = "mistral-chat-app/1.0 (weather app)"


class WeatherConditions(BaseModel):
    temperature: float
    apparent_temperature: float
    humidity: int
    wind_speed: float
    weather_code: int
    is_day: bool


class CurrentWeather(BaseModel):
    latitude: float
    longitude: float
    location_name: str | None = None
    conditions: WeatherConditions


class City(BaseModel):
    name: str
    latitude: float
    longitude: float


class CurrentConditions(BaseModel):
    """The current weather fields this app reads from the Open-Meteo API."""

    temperature: float = Field(alias="temperature_2m")
    apparent_temperature: float
    humidity: int = Field(alias="relative_humidity_2m")
    wind_speed: float = Field(alias="wind_speed_10m")
    weather_code: int
    is_day: int


CURRENT_FIELDS = "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day"


async def fetch_current_conditions(client: httpx.AsyncClient, latitude: float, longitude: float) -> CurrentWeather:
    response = await client.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": CURRENT_FIELDS,
            "timezone": "auto",
        },
        headers={"User-Agent": USER_AGENT},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="The Open-Meteo API did not answer.")

    body = response.json()
    current = CurrentConditions.model_validate(body["current"])
    return CurrentWeather(
        latitude=latitude,
        longitude=longitude,
        conditions=WeatherConditions(
            temperature=current.temperature,
            apparent_temperature=current.apparent_temperature,
            humidity=current.humidity,
            wind_speed=current.wind_speed,
            weather_code=current.weather_code,
            is_day=current.is_day == 1,
        ),
    )


class GeocodedPlace(BaseModel):
    """A place the Open-Meteo geocoding API resolved a location name to."""

    name: str
    latitude: float
    longitude: float


async def geocode(client: httpx.AsyncClient, name: str) -> GeocodedPlace | None:
    """The first populated place the Open-Meteo geocoding API finds for ``name``, or None."""

    response = await client.get(
        OPEN_METEO_GEOCODING_URL,
        params={"name": name, "count": 10, "language": "en"},
        headers={"User-Agent": USER_AGENT},
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="The Open-Meteo geocoding API did not answer.")

    results = response.json().get("results") or []
    for hit in results:
        if hit.get("feature_code") not in ("PPLC", "PPL", "PPLA", "PPLA2", "PPLA3", "PPLG", "PPLL", "PPLS", "PPLX"):
            continue
        return GeocodedPlace(
            name=f"{hit.get('name', '')}, {hit.get('country', '')}".strip(", "),
            latitude=hit["latitude"],
            longitude=hit["longitude"],
        )
    return None


CITIES: list[City] = [
    City(name="New York", latitude=40.7128, longitude=-74.0060),
    City(name="London", latitude=51.5072, longitude=-0.1276),
    City(name="Paris", latitude=48.8566, longitude=2.3522),
    City(name="Berlin", latitude=52.5200, longitude=13.4050),
    City(name="Casablanca", latitude=33.5731, longitude=-7.5898),
    City(name="Cairo", latitude=30.0444, longitude=31.2357),
    City(name="Lagos", latitude=6.5244, longitude=3.3792),
    City(name="Nairobi", latitude=-1.2921, longitude=36.8219),
    City(name="Cape Town", latitude=-33.9249, longitude=18.4241),
    City(name="Dubai", latitude=25.2048, longitude=55.2708),
    City(name="Mumbai", latitude=19.0760, longitude=72.8777),
    City(name="Delhi", latitude=28.6139, longitude=77.2090),
    City(name="Bangkok", latitude=13.7563, longitude=100.5018),
    City(name="Singapore", latitude=1.3521, longitude=103.8198),
    City(name="Jakarta", latitude=-6.2088, longitude=106.8456),
    City(name="Shanghai", latitude=31.2304, longitude=121.4737),
    City(name="Beijing", latitude=39.9042, longitude=116.4074),
    City(name="Tokyo", latitude=35.6762, longitude=139.6503),
    City(name="Seoul", latitude=37.5665, longitude=126.9780),
    City(name="Sydney", latitude=-33.8688, longitude=151.2093),
    City(name="Auckland", latitude=-36.8485, longitude=174.7633),
    City(name="São Paulo", latitude=-23.5505, longitude=-46.6333),
    City(name="Buenos Aires", latitude=-34.6037, longitude=-58.3816),
    City(name="Mexico City", latitude=19.4326, longitude=-99.1332),
    City(name="Los Angeles", latitude=34.0522, longitude=-118.2437),
    City(name="Chicago", latitude=41.8781, longitude=-87.6298),
    City(name="Toronto", latitude=43.6532, longitude=-79.3832),
    City(name="Vancouver", latitude=49.2827, longitude=-123.1207),
    City(name="Reykjavík", latitude=64.1466, longitude=-21.9426),
    City(name="Moscow", latitude=55.7558, longitude=37.6173),
]


router = APIRouter()


@router.get(
    "/cities",
    operation_id="v1_weather_cities",
    summary="The curated major cities shown on the map",
)
async def weather_cities() -> list[City]:
    return CITIES


@router.get(
    "/current",
    operation_id="v1_weather_current",
    summary="Current weather for a point, from the Open-Meteo API",
)
async def weather_current(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
) -> CurrentWeather:
    async with httpx.AsyncClient(timeout=15) as client:
        return await fetch_current_conditions(client, latitude, longitude)
