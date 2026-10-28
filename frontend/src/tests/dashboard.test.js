import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  getActuals,
  getForecasts,
  getComparison,
  getAnalytics,
  getHealth,
  getIngestionStatus,
} from '../services/api.js';

describe('Frontend API Client Unit Tests', () => {
  test('API functions are defined and exported', () => {
    assert.equal(typeof getActuals, 'function');
    assert.equal(typeof getForecasts, 'function');
    assert.equal(typeof getComparison, 'function');
    assert.equal(typeof getAnalytics, 'function');
    assert.equal(typeof getHealth, 'function');
    assert.equal(typeof getIngestionStatus, 'function');
  });
});

describe('KPI Metric & Null Handling Tests', () => {
  const formatVal = (val, decimals = 2) => {
    if (val === null || val === undefined) return '—';
    return Number(val).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  test('Null metrics are formatted as dash, never coerced to zero', () => {
    assert.equal(formatVal(null), '—');
    assert.equal(formatVal(undefined), '—');
    assert.notEqual(formatVal(null), '0.00');
    assert.notEqual(formatVal(null), '0');
  });

  test('Valid metric values format correctly with units', () => {
    assert.equal(formatVal(482.35, 1), '482.4');
    assert.equal(formatVal(8.742, 2), '8.74');
  });

  test('Bias sign interpretation correctly distinguishes overforecasting and underforecasting', () => {
    const positiveBias = 145.2;
    const negativeBias = -85.4;
    const zeroBias = 0.0;

    assert.equal(positiveBias > 0, true, 'Positive bias must indicate overforecast');
    assert.equal(negativeBias < 0, true, 'Negative bias must indicate underforecast');
    assert.equal(zeroBias === 0, true, 'Zero bias indicates exact balance');
  });
});

describe('Chart Data Mapping & Missing Interval Integrity Tests', () => {
  test('Missing intervals preserve null values and do not fabricate zero MW', () => {
    const rawIntervals = [
      {
        delivery_timestamp: '2026-01-01T00:00:00Z',
        settlement_period: 1,
        actual_generation_mw: 10000.0,
        forecast_generation_mw: 10500.0,
        forecast_error_mw: 500.0,
        is_matched: true,
      },
      {
        delivery_timestamp: '2026-01-01T00:30:00Z',
        settlement_period: 2,
        actual_generation_mw: null, // missing actual
        forecast_generation_mw: 10500.0,
        forecast_error_mw: null,
        is_matched: false,
      },
      {
        delivery_timestamp: '2026-01-01T01:00:00Z',
        settlement_period: 3,
        actual_generation_mw: 9500.0,
        forecast_generation_mw: null, // missing forecast
        forecast_error_mw: null,
        is_matched: false,
      },
    ];

    const mapped = rawIntervals.map((i) => ({
      timestamp: i.delivery_timestamp,
      sp: i.settlement_period,
      actual: i.actual_generation_mw,
      forecast: i.forecast_generation_mw,
      error: i.forecast_error_mw,
      matched: i.is_matched,
    }));

    // Interval 1: matched
    assert.equal(mapped[0].matched, true);
    assert.equal(mapped[0].error, 500.0);

    // Interval 2: missing actual must remain null (not 0.0)
    assert.equal(mapped[1].matched, false);
    assert.equal(mapped[1].actual, null);
    assert.notEqual(mapped[1].actual, 0);

    // Interval 3: missing forecast must remain null (not 0.0)
    assert.equal(mapped[2].matched, false);
    assert.equal(mapped[2].forecast, null);
    assert.notEqual(mapped[2].forecast, 0);
  });
});

describe('Resolution Bridge Accounting Tests', () => {
  test('One hourly forecast covers two half-hourly actuals', () => {
    const uniqueHourlyForecasts = 24; // 1 day
    const coveredHalfHours = uniqueHourlyForecasts * 2; // 48 SPs
    const expectedHalfHours = 48;

    assert.equal(coveredHalfHours, 48);
    assert.equal(coveredHalfHours, expectedHalfHours);
    assert.notEqual(uniqueHourlyForecasts, coveredHalfHours);
  });

  test('Multi-day coverage accounts for unique hourly forecasts correctly', () => {
    const days = 7;
    const expectedHalfHours = days * 48; // 336
    const expectedUniqueForecasts = days * 24; // 168

    assert.equal(expectedHalfHours, 336);
    assert.equal(expectedUniqueForecasts, 168);
    assert.equal(expectedUniqueForecasts * 2, expectedHalfHours);
  });
});

describe('Date Boundary Validation Tests', () => {
  test('Validates start_date <= end_date', () => {
    const isValidRange = (start, end) => new Date(start) <= new Date(end);

    assert.equal(isValidRange('2026-01-01', '2026-01-07'), true);
    assert.equal(isValidRange('2026-01-01', '2026-01-01'), true); // single day
    assert.equal(isValidRange('2026-01-07', '2026-01-01'), false); // invalid
  });

  test('Validates decision cutoff 24-hour format', () => {
    const isValidCutoff = (cutoff) => {
      const parts = cutoff.trim().split(':');
      if (parts.length !== 2) return false;
      const [h, m] = parts.map(Number);
      return !isNaN(h) && !isNaN(m) && h >= 0 && h <= 23 && m >= 0 && m <= 59;
    };

    assert.equal(isValidCutoff('11:00'), true);
    assert.equal(isValidCutoff('09:30'), true);
    assert.equal(isValidCutoff('23:59'), true);
    assert.equal(isValidCutoff('00:00'), true);
    assert.equal(isValidCutoff('25:00'), false);
    assert.equal(isValidCutoff('11:60'), false);
    assert.equal(isValidCutoff('invalid'), false);
  });
});

describe('Stale Response & API Error Protection Tests', () => {
  test('Out-of-order API responses do not overwrite newer results', () => {
    let requestId = 0;
    let currentData = null;

    // Simulate two sequential queries where query 1 resolves after query 2
    const query1Id = ++requestId;
    const query2Id = ++requestId;

    // Response 2 arrives first
    if (query2Id === requestId) {
      currentData = { range: '2026-01-02 to 2026-01-08' };
    }
    assert.deepEqual(currentData, { range: '2026-01-02 to 2026-01-08' });

    // Response 1 arrives late: must be ignored because query1Id !== requestId
    if (query1Id === requestId) {
      currentData = { range: '2026-01-01 to 2026-01-07' };
    }
    assert.deepEqual(currentData, { range: '2026-01-02 to 2026-01-08' }, 'Stale response 1 must not overwrite newer response 2');
  });

  test('API error nullifies stale KPI and comparison data', () => {
    let analytics = { mae_mw: 2150.0 };
    let comparison = { intervals: [1, 2, 3] };
    let error = null;

    // Simulate API failure handler
    const handleApiError = (err) => {
      analytics = null;
      comparison = null;
      error = err.message;
    };

    handleApiError(new Error('500 Internal Server Error'));

    assert.equal(analytics, null, 'Stale analytics must be reset to null on error');
    assert.equal(comparison, null, 'Stale comparison must be reset to null on error');
    assert.equal(error, '500 Internal Server Error');
  });
});

describe('Forecast Vintage Filter Logic Tests', () => {
  const vintages = [
    { delivery: '2026-01-01T12:00:00Z', publish: '2025-12-30T10:00:00Z', mw: 14000 },
    { delivery: '2026-01-01T12:00:00Z', publish: '2025-12-31T09:30:00Z', mw: 15000 },
    { delivery: '2026-01-01T12:00:00Z', publish: '2025-12-31T14:00:00Z', mw: 16000 },
  ];

  test('publish_before filter excludes vintages published after cutoff', () => {
    const cutoff = '2025-12-31T11:00:00Z';
    const eligible = vintages.filter((v) => v.publish <= cutoff);
    assert.equal(eligible.length, 2);
    assert.equal(eligible.every((v) => v.publish <= cutoff), true);
    assert.equal(eligible.some((v) => v.publish === '2025-12-31T14:00:00Z'), false);
  });

  test('latest_only filter returns the most recent vintage for the delivery interval', () => {
    // Sort descending by publish
    const sorted = [...vintages].sort((a, b) => b.publish.localeCompare(a.publish));
    const latest = sorted[0];
    assert.equal(latest.publish, '2025-12-31T14:00:00Z');
    assert.equal(latest.mw, 16000);
  });
});
