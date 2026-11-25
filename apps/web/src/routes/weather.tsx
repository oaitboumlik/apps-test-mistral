import { createFileRoute, Link } from "@tanstack/react-router";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useCallback, useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";

import { unwrap } from "../api/unwrap";
import { v1WeatherCities, v1WeatherCurrent } from "../api/generated/sdk.gen";
import type { City, CurrentWeather } from "../api/generated/types.gen";

interface CityWeather extends City {
  weather: CurrentWeather | null;
}

const WEATHER_CODES: Record<number, string> = {
  0: "Clear",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Fog",
  51: "Drizzle",
  53: "Drizzle",
  55: "Drizzle",
  61: "Slight rain",
  63: "Rain",
  65: "Heavy rain",
  71: "Slight snow",
  73: "Snow",
  75: "Heavy snow",
  77: "Snow grains",
  80: "Rain showers",
  81: "Rain showers",
  82: "Heavy showers",
  85: "Snow showers",
  86: "Snow showers",
  95: "Thunderstorm",
  96: "Thunderstorm, hail",
  99: "Thunderstorm, hail",
};

const describe = (code: number) => WEATHER_CODES[code] ?? "Unknown";

const temperatureColor = (temperature: number) => {
  if (temperature >= 30) return "#d64545";
  if (temperature >= 20) return "#e08b3a";
  if (temperature >= 10) return "#d8b13a";
  if (temperature >= 0) return "#4b9bc0";
  return "#4b6cb7";
};

const Conditions = ({ weather, name }: { weather: CurrentWeather; name?: string | null }) => (
  <div className="space-y-1">
    {name ? <p className="font-semibold">{name}</p> : null}
    <p className="text-lg font-semibold">{weather.conditions.temperature.toFixed(1)} °C</p>
    <p>{describe(weather.conditions.weather_code)}</p>
    <p className="text-xs opacity-70">
      Feels {weather.conditions.apparent_temperature.toFixed(1)} °C · Humidity {weather.conditions.humidity}% ·{" "}
      Wind {weather.conditions.wind_speed.toFixed(1)} km/h
    </p>
  </div>
);

const ClickHandler = ({ onPick }: { onPick: (lat: number, lon: number) => void }) => {
  useMapEvents({
    click: (event) => {
      onPick(event.latlng.lat, event.latlng.lng);
    },
  });
  return null;
};

const FitWorld = () => {
  const map = useMap();
  useEffect(() => {
    map.fitWorld();
  }, [map]);
  return null;
};

const WeatherMap = () => {
  const [cities, setCities] = useState<CityWeather[]>([]);
  const [picked, setPicked] = useState<(CurrentWeather & { name: string | null }) | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      const list = await unwrap(v1WeatherCities());
      if (cancelled) {
        return;
      }
      setCities(list.map((city) => ({ ...city, weather: null })));
      await Promise.all(
        list.map(async (city) => {
          const weather = await unwrap(
            v1WeatherCurrent({ query: { latitude: city.latitude, longitude: city.longitude } }),
          );
          if (!cancelled) {
            setCities((current) =>
              current.map((entry) => (entry.name === city.name ? { ...entry, weather } : entry)),
            );
          }
        }),
      );
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const pick = useCallback(async (latitude: number, longitude: number) => {
    const weather = await unwrap(v1WeatherCurrent({ query: { latitude, longitude } }));
    setPicked({ ...weather, name: null });
  }, []);

  return (
    <MapContainer className="size-full" zoom={3} center={[20, 10]} minZoom={2} worldCopyJump>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Weather &copy; <a href="https://open-meteo.com/">Open-Meteo</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickHandler onPick={(lat, lon) => void pick(lat, lon)} />
      <FitWorld />
      {cities.map((city) => (
        <CircleMarker
          key={city.name}
          center={[city.latitude, city.longitude]}
          radius={8}
          pathOptions={{
            color: temperatureColor(city.weather?.conditions.temperature ?? 10),
            fillColor: temperatureColor(city.weather?.conditions.temperature ?? 10),
            fillOpacity: 0.8,
          }}
        >
          {city.weather ? (
            <Tooltip direction="top" offset={[0, -6]}>
              {city.name}: {city.weather.conditions.temperature.toFixed(0)} °C
            </Tooltip>
          ) : null}
          {city.weather ? (
            <Popup>
              <Conditions weather={city.weather} name={city.name} />
            </Popup>
          ) : null}
        </CircleMarker>
      ))}
      {picked ? (
        <CircleMarker
          center={[picked.latitude, picked.longitude]}
          radius={10}
          pathOptions={{ color: "#222", fillColor: "#222", fillOpacity: 0.7 }}
        >
          <Popup>
            <Conditions weather={picked} name={picked.name ?? "Picked location"} />
          </Popup>
        </CircleMarker>
      ) : null}
    </MapContainer>
  );
};

const Weather = () => (
  <main className="flex h-full flex-col">
    <header className="flex items-center justify-between gap-4 px-4 py-2">
      <h1 className="text-lg font-semibold">World weather</h1>
      <Link className="text-sm underline" to="/chat">
        Ask the weather assistant →
      </Link>
    </header>
    <p className="px-4 pb-2 text-xs opacity-60">
      Circle markers show current temperature at major cities. Click anywhere to read the weather there.
    </p>
    <div className="min-h-0 flex-1">
      <WeatherMap />
    </div>
  </main>
);

export const Route = createFileRoute("/weather")({
  staticData: { landing: true },
  component: Weather,
});
