"""Asynchronous HTTP Client for Elexon BMRS / Insights Solution API.

Responsibilities:
1. Stream fetching for FUELHH (Actual generation by fuel type) with WIND filtering.
2. Stream fetching for WINDFOR (Wind generation forecasts) preserving dual timestamps
   (target delivery interval startTime and forecast vintage publishTime).
3. Configurable chunking (default 3-day windows) to avoid timeouts.
4. Retry logic with exponential backoff on HTTP 429 and 5xx transient server errors.
5. Strict validation into Pydantic models (FuelhhWindRecord, WindforForecastRecord).
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import httpx

from backend.app.core.config import settings
from backend.app.core.timezone import format_utc_iso, ensure_utc
from backend.app.schemas.elexon import FuelhhWindRecord, WindforForecastRecord

logger = logging.getLogger(__name__)


class ElexonError(Exception):
    """Base exception for Elexon API interactions."""
    pass


class ElexonRateLimitError(ElexonError):
    """Raised when Elexon returns HTTP 429 and retries are exhausted."""
    pass


class ElexonClient:
    """Async client for querying Elexon BMRS streaming endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_factor: float = 0.5,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = (base_url or settings.ELEXON_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.ELEXON_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.ELEXON_MAX_RETRIES
        self.backoff_factor = backoff_factor
        self._external_client = client
        self._internal_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        if self._external_client is None:
            self._internal_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._internal_client:
            await self._internal_client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._external_client:
            return self._external_client
        if self._internal_client is None:
            self._internal_client = httpx.AsyncClient(timeout=self.timeout)
        return self._internal_client

    async def close(self):
        if self._internal_client:
            await self._internal_client.aclose()
            self._internal_client = None

    async def _request_with_retry(
        self,
        endpoint_path: str,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute GET request with exponential backoff for transient 429 and 5xx errors."""
        url = f"{self.base_url}/{endpoint_path.lstrip('/')}"
        attempt = 0

        while attempt <= self.max_retries:
            try:
                logger.debug(f"Requesting {url} with params {params} (attempt {attempt + 1})")
                response = await self.client.get(url, params=params)

                # Check for rate limiting
                if response.status_code == 429:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise ElexonRateLimitError(f"Rate limit exceeded on {url} after {self.max_retries} retries.")
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after else (self.backoff_factor * (2 ** attempt))
                    logger.warning(f"HTTP 429 Rate Limit. Sleeping {sleep_time:.2f}s before retry {attempt}...")
                    await asyncio.sleep(sleep_time)
                    continue

                # Check for 5xx transient server errors
                if 500 <= response.status_code < 600:
                    attempt += 1
                    if attempt > self.max_retries:
                        response.raise_for_status()
                    sleep_time = self.backoff_factor * (2 ** attempt)
                    logger.warning(f"Server error HTTP {response.status_code}. Sleeping {sleep_time:.2f}s before retry {attempt}...")
                    await asyncio.sleep(sleep_time)
                    continue

                # Raise for any 4xx client errors
                response.raise_for_status()

                # Parse JSON stream response
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # In some non-stream endpoints, records are nested under 'data'
                    return data.get("data", [])
                return []

            except (httpx.TransportError, httpx.TimeoutException) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise ElexonError(f"Network transport error connecting to {url}: {exc}") from exc
                sleep_time = self.backoff_factor * (2 ** attempt)
                logger.warning(f"Transport error {exc}. Sleeping {sleep_time:.2f}s before retry {attempt}...")
                await asyncio.sleep(sleep_time)

        raise ElexonError(f"Failed to fetch data from {url} after {self.max_retries} retries.")

    def _split_date_range(self, start_date: date, end_date: date, chunk_days: int) -> List[Tuple[date, date]]:
        """Split a [start_date, end_date] range into smaller inclusive slices."""
        slices = []
        current_start = start_date
        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=chunk_days - 1), end_date)
            slices.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)
        return slices

    def _split_datetime_range(
        self,
        start_dt: datetime,
        end_dt: datetime,
        chunk_days: int
    ) -> List[Tuple[datetime, datetime]]:
        """Split a [start_dt, end_dt] UTC window into smaller slices."""
        slices = []
        current_start = ensure_utc(start_dt)
        end_utc = ensure_utc(end_dt)
        chunk_delta = timedelta(days=chunk_days)

        while current_start < end_utc:
            current_end = min(current_start + chunk_delta, end_utc)
            slices.append((current_start, current_end))
            current_start = current_end
        return slices

    async def fetch_fuelhh_raw(self, settlement_date_from: date, settlement_date_to: date) -> List[Dict[str, Any]]:
        """Fetch raw FUELHH stream for the specified settlement date window."""
        params = {
            "settlementDateFrom": settlement_date_from.isoformat(),
            "settlementDateTo": settlement_date_to.isoformat(),
        }
        return await self._request_with_retry("datasets/FUELHH/stream", params)

    async def fetch_actual_wind_generation(
        self,
        settlement_date_from: date,
        settlement_date_to: date,
        chunk_days: int = 3
    ) -> List[FuelhhWindRecord]:
        """Fetch and validate actual wind generation for a settlement date range.
        
        Splits request into chunk_days (default 3 days), filters fuelType == 'WIND',
        and validates into FuelhhWindRecord models.
        """
        slices = self._split_date_range(settlement_date_from, settlement_date_to, chunk_days)
        all_records: List[FuelhhWindRecord] = []
        seen_keys = set()

        for chunk_start, chunk_end in slices:
            raw_records = await self.fetch_fuelhh_raw(chunk_start, chunk_end)
            for item in raw_records:
                fuel_type = str(item.get("fuelType", "")).upper()
                if fuel_type != "WIND":
                    continue

                try:
                    # Map API fields to schema
                    rec = FuelhhWindRecord(
                        start_time=item["startTime"],
                        settlement_date=item["settlementDate"],
                        settlement_period=item["settlementPeriod"],
                        generation_mw=item["generation"],
                        fuel_type="WIND",
                        publish_time=item.get("publishTime"),
                        dataset=item.get("dataset", "FUELHH"),
                    )
                    
                    # Deduplicate across (start_time, fuel_type)
                    key = (rec.start_time, rec.fuel_type)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_records.append(rec)

                except Exception as val_err:
                    logger.warning(f"Skipping invalid FUELHH record: {item}. Error: {val_err}")

        # Sort chronologically by start_time
        all_records.sort(key=lambda r: r.start_time)
        return all_records

    async def fetch_windfor_raw(
        self,
        publish_time_from: datetime,
        publish_time_to: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch raw WINDFOR stream for the specified forecast publication window."""
        params = {
            "publishDateTimeFrom": format_utc_iso(publish_time_from),
            "publishDateTimeTo": format_utc_iso(publish_time_to),
        }
        return await self._request_with_retry("datasets/WINDFOR/stream", params)

    async def fetch_wind_forecasts(
        self,
        publish_time_from: datetime,
        publish_time_to: datetime,
        target_delivery_start: Optional[datetime] = None,
        target_delivery_end: Optional[datetime] = None,
        ex_ante_only: bool = False,
        chunk_days: int = 3
    ) -> List[WindforForecastRecord]:
        """Fetch and validate wind forecasts published within [publish_time_from, publish_time_to].
        
        Preserves delivery startTime and vintage publishTime.
        
        Parameters:
        - publish_time_from / publish_time_to: The window of publication timestamps.
        - target_delivery_start / target_delivery_end: Optional bounds to filter forecast delivery startTime.
        - ex_ante_only: If True, filters out retrospective records where publish_time > start_time.
          NESO's 72-hour sliding batches typically include the preceding 6 to 26 hours as an anchor;
          setting ex_ante_only=True ensures only forecasts published before or at delivery are returned.
        - chunk_days: Window chunk size in days (default 3).
        """
        slices = self._split_datetime_range(publish_time_from, publish_time_to, chunk_days)
        all_forecasts: List[WindforForecastRecord] = []
        seen_keys = set()

        deliv_start_utc = ensure_utc(target_delivery_start) if target_delivery_start else None
        deliv_end_utc = ensure_utc(target_delivery_end) if target_delivery_end else None

        for chunk_start, chunk_end in slices:
            raw_records = await self.fetch_windfor_raw(chunk_start, chunk_end)
            for item in raw_records:
                try:
                    rec = WindforForecastRecord(
                        start_time=item["startTime"],
                        publish_time=item["publishTime"],
                        generation_mw=item["generation"],
                        dataset=item.get("dataset", "WINDFOR"),
                    )

                    # Ex-ante filtering if requested
                    if ex_ante_only and not rec.is_ex_ante:
                        continue

                    # Optional target delivery window filtering
                    if deliv_start_utc and rec.start_time < deliv_start_utc:
                        continue
                    if deliv_end_utc and rec.start_time >= deliv_end_utc:
                        continue

                    # Deduplicate across (start_time, publish_time)
                    key = (rec.start_time, rec.publish_time)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_forecasts.append(rec)

                except Exception as val_err:
                    logger.warning(f"Skipping invalid WINDFOR record: {item}. Error: {val_err}")

        # Sort by target delivery start_time, then publication time
        all_forecasts.sort(key=lambda r: (r.start_time, r.publish_time))
        return all_forecasts
