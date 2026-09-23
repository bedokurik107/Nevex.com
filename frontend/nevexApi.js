const API_BASE = import.meta?.env?.VITE_API_BASE_URL || "";

async function apiFetch(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `NEVEX API error: ${response.status}`);
  }
  return response.json();
}

export async function getGifts(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  });
  return apiFetch(`/api/gifts${query.toString() ? `?${query}` : ""}`);
}

export async function getGift(slug) {
  return apiFetch(`/api/gifts/${encodeURIComponent(slug)}`);
}
