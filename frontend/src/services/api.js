import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL ? `${import.meta.env.VITE_API_BASE_URL}/api` : '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Health check endpoint
 */
export const getHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

/**
 * Ingestion status endpoint
 */
export const getIngestionStatus = async () => {
  const response = await api.get('/ingestion/status');
  return response.data;
};

/**
 * Actuals endpoint: GET /api/actuals
 * @param {string} startDate - 'YYYY-MM-DD'
 * @param {string} endDate - 'YYYY-MM-DD'
 */
export const getActuals = async (startDate, endDate) => {
  const response = await api.get('/actuals', {
    params: { start_date: startDate, end_date: endDate },
  });
  return response.data;
};

/**
 * Forecasts endpoint: GET /api/forecasts
 * @param {string} startDate - 'YYYY-MM-DD'
 * @param {string} endDate - 'YYYY-MM-DD'
 * @param {boolean} latestOnly - If true, only latest vintage per delivery hour
 * @param {string|null} publishBefore - Optional UTC ISO-8601 upper bound
 */
export const getForecasts = async (startDate, endDate, latestOnly = false, publishBefore = null) => {
  const params = {
    start_date: startDate,
    end_date: endDate,
    latest_only: latestOnly,
  };
  if (publishBefore) {
    params.publish_before = publishBefore;
  }
  const response = await api.get('/forecasts', { params });
  return response.data;
};

/**
 * Forecast vs. Actual comparison endpoint: GET /api/comparison
 * @param {string} startDate - 'YYYY-MM-DD'
 * @param {string} endDate - 'YYYY-MM-DD'
 * @param {string} decisionCutoff - 'HH:MM' (default '11:00')
 */
export const getComparison = async (startDate, endDate, decisionCutoff = '11:00') => {
  const response = await api.get('/comparison', {
    params: {
      start_date: startDate,
      end_date: endDate,
      decision_cutoff: decisionCutoff,
    },
  });
  return response.data;
};

/**
 * Forecast accuracy analytics endpoint: GET /api/analytics
 * @param {string} startDate - 'YYYY-MM-DD'
 * @param {string} endDate - 'YYYY-MM-DD'
 * @param {string} decisionCutoff - 'HH:MM' (default '11:00')
 */
export const getAnalytics = async (startDate, endDate, decisionCutoff = '11:00') => {
  const response = await api.get('/analytics', {
    params: {
      start_date: startDate,
      end_date: endDate,
      decision_cutoff: decisionCutoff,
    },
  });
  return response.data;
};

export default api;
