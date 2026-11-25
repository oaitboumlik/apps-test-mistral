import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import MockTransport

from conftest import build_app

GEOCODING_BODY = {
    "results": [
        {
            "name": "Paris",
            "country": "France",
            "latitude": 48.85,
            "longitude": 2.35,
            "feature_code": "PPLC",
            "population": 2_100_000,
        }
    ]
}

FORECAST_BODY = {
    "latitude": 48.85,
    "longitude": 2.35,
    "current": {
        "temperature_2m": 12.3,
        "apparent_temperature": 11.0,
        "relative_humidity_2m": 71,
        "wind_speed_10m": 9.8,
        "weather_code": 2,
        "is_day": 1,
    },
}


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _mock_open_meteo() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in str(request.url):
            return httpx.Response(200, json=GEOCODING_BODY)
        return httpx.Response(200, json=FORECAST_BODY)

    return _REAL_ASYNC_CLIENT(transport=MockTransport(handler))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: _mock_open_meteo())
    return TestClient(build_app())


def test_cities_lists_the_curated_major_cities(client: TestClient) -> None:
    res = client.get("/api/v1/weather/cities")

    assert res.status_code == 200
    names = [city["name"] for city in res.json()]
    assert "Paris" in names
    assert len(names) >= 20


def test_current_normalizes_the_open_meteo_answer(client: TestClient) -> None:
    res = client.get("/api/v1/weather/current", params={"latitude": 48.85, "longitude": 2.35})

    assert res.status_code == 200
    data = res.json()
    assert data["latitude"] == 48.85
    assert data["conditions"]["temperature"] == pytest.approx(12.3)
    assert data["conditions"]["humidity"] == 71
    assert data["conditions"]["weather_code"] == 2
    assert data["conditions"]["is_day"] is True


def test_current_refuses_out_of_range_coordinates(client: TestClient) -> None:
    res = client.get("/api/v1/weather/current", params={"latitude": 91, "longitude": 0})

    assert res.status_code == 422


def test_current_maps_an_upstream_failure_to_a_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    def broken_client(**_kwargs: object) -> httpx.AsyncClient:
        return _REAL_ASYNC_CLIENT(transport=MockTransport(broken))

    monkeypatch.setattr(httpx, "AsyncClient", broken_client)
    res = client.get("/api/v1/weather/current", params={"latitude": 48.85, "longitude": 2.35})

    assert res.status_code == 502
