const TOKEN_KEY = "agritech_token";

function currentPagePath() {
  const path = window.location.pathname || "";
  const file = path.split("/").pop();
  return file || "dashboard.html";
}

export function checkAuth() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) return true;

  const redirect = encodeURIComponent(currentPagePath());
  window.location.replace(`index.html?redirect=${redirect}`);
  return false;
}

export function getRedirectParam() {
  const redirect = new URLSearchParams(window.location.search).get("redirect");
  if (!redirect) return null;

  // Only allow same-folder html targets to avoid open redirects.
  const cleaned = redirect.replace(/^\//, "").trim();
  if (!/^[a-z0-9_-]+\.html$/i.test(cleaned)) return null;
  return cleaned;
}

export function storeAuthToken(token) {
  if (!token) return;
  localStorage.setItem(TOKEN_KEY, token);
}

