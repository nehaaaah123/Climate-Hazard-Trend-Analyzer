/**
 * API client module for Climate Hazard Trend Analyzer.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export async function fetchRegions() {
  const response = await fetch(`${API_BASE_URL}/api/v1/regions`);
  if (!response.ok) {
    throw new Error(`Failed to load preset regions (${response.status})`);
  }
  return response.json();
}

export async function fetchHeatwaveAnalysis(params) {
  const queryParams = new URLSearchParams();

  if (params.bbox) {
    queryParams.set('bbox', params.bbox);
  } else {
    if (params.lat !== undefined && params.lat !== null) queryParams.set('lat', params.lat);
    if (params.lon !== undefined && params.lon !== null) queryParams.set('lon', params.lon);
  }

  if (params.start_year) queryParams.set('start_year', params.start_year);
  if (params.end_year) queryParams.set('end_year', params.end_year);
  if (params.percentile) queryParams.set('percentile', params.percentile);
  if (params.min_days) queryParams.set('min_days', params.min_days);
  if (params.hazard_type) queryParams.set('hazard_type', params.hazard_type);

  const url = `${API_BASE_URL}/api/v1/analysis/heatwave?${queryParams.toString()}`;

  const response = await fetch(url);

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After') || '60';
    const err = new Error(`Rate limit exceeded (30 req/min). Please wait ${retryAfter}s before retrying.`);
    err.status = 429;
    err.retryAfter = retryAfter;
    throw err;
  }

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch (_) {
      errorData = { message: `Request failed with status ${response.status}` };
    }
    const err = new Error(errorData.message || 'Analysis request failed');
    err.details = errorData.details;
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export async function fetchPaginatedEvents(params, page = 1, pageSize = 10) {
  const queryParams = new URLSearchParams();

  if (params.bbox) {
    queryParams.set('bbox', params.bbox);
  } else {
    if (params.lat !== undefined) queryParams.set('lat', params.lat);
    if (params.lon !== undefined) queryParams.set('lon', params.lon);
  }

  queryParams.set('start_year', params.start_year || 1990);
  queryParams.set('end_year', params.end_year || 2023);
  queryParams.set('percentile', params.percentile || 95);
  queryParams.set('min_days', params.min_days || 3);
  queryParams.set('page', page);
  queryParams.set('page_size', pageSize);

  const url = `${API_BASE_URL}/api/v1/analysis/heatwave/events?${queryParams.toString()}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error('Failed to fetch paginated events');
  }
  return response.json();
}

export function getExportUrl(format = 'csv', params) {
  const queryParams = new URLSearchParams();

  if (params.bbox) {
    queryParams.set('bbox', params.bbox);
  } else {
    if (params.lat !== undefined) queryParams.set('lat', params.lat);
    if (params.lon !== undefined) queryParams.set('lon', params.lon);
  }

  if (params.start_year) queryParams.set('start_year', params.start_year);
  if (params.end_year) queryParams.set('end_year', params.end_year);
  if (params.percentile) queryParams.set('percentile', params.percentile);
  if (params.min_days) queryParams.set('min_days', params.min_days);
  if (params.hazard_type) queryParams.set('hazard_type', params.hazard_type);

  return `${API_BASE_URL}/api/v1/export/${format}?${queryParams.toString()}`;
}

