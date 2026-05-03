const JSON_HDR = { "Content-Type": "application/json" };

/**
 * @returns {Promise<{ res: Response, data: object }>}
 */
export async function login(email, password) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: JSON_HDR,
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

/**
 * @param {object} payload - email, password, first_name, last_name, phone
 */
export async function register(payload) {
  const res = await fetch("/api/signup", {
    method: "POST",
    headers: JSON_HDR,
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

/**
 * @param {FormData} formData - must include image file under key 'image'
 */
export async function detect(formData) {
  const res = await fetch("/api/detect", {
    method: "POST",
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

/**
 * Geocode a city name via Open-Meteo (no API key).
 * @returns {Promise<object|null>} first result or null
 */
export async function geocodeCity(city) {
  const r = await fetch(
    `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=en&format=json`
  );
  if (!r.ok) return null;
  const geo = await r.json();
  return geo.results && geo.results[0] ? geo.results[0] : null;
}

/**
 * Open-Meteo 7-day forecast + current fields.
 */
export async function fetchOpenMeteoForecast(lat, lon) {
  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.searchParams.set("latitude", String(lat));
  url.searchParams.set("longitude", String(lon));
  url.searchParams.set("timezone", "auto");
  url.searchParams.set("wind_speed_unit", "ms");
  url.searchParams.set("forecast_days", "7");
  url.searchParams.set(
    "daily",
    "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,sunrise,sunset"
  );
  url.searchParams.set(
    "current",
    "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,surface_pressure,uv_index"
  );
  const res = await fetch(url.toString());
  const data = await res.json().catch(() => null);
  return { ok: res.ok, data };
}

/**
 * High-level weather helper: resolve city name to forecast payload.
 * @returns {Promise<{ ok: boolean, locationLabel: string, forecast: object|null, error?: string }>}
 */
export async function getWeather(city) {
  try {
    const place = await geocodeCity(city);
    if (!place) return { ok: false, locationLabel: "", forecast: null, error: "City not found" };
    const label = [place.name, place.admin1, place.country_code].filter(Boolean).join(", ");
    const { ok, data } = await fetchOpenMeteoForecast(place.latitude, place.longitude);
    if (!ok || !data) return { ok: false, locationLabel: label, forecast: null, error: "Forecast failed" };
    return { ok: true, locationLabel: label, forecast: data };
  } catch (e) {
    return { ok: false, locationLabel: "", forecast: null, error: String(e.message || e) };
  }
}

export async function submitContact(data) {
  const res = await fetch("/api/contact", {
    method: "POST",
    headers: JSON_HDR,
    body: JSON.stringify(data),
  });
  const body = await res.json().catch(() => ({}));
  return { res, data: body };
}
