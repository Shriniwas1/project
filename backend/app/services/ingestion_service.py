"""Data Ingestion Service for UK National Wind Actuals and Forecasts.

Enforces:
1. Native resolutions: 30-min settlement actuals (FUELHH), 1-hour forecasts (WINDFOR).
2. Timezone-aware UTC normalization and Europe/London delivery date derivation.
3. Multi-vintage preservation for forecasts (never overwrite earlier publication timestamps).
4. Idempotent upserts / duplicate skipping in atomic transactions.
5. Ingestion audit logging in `ingestion_log`.
6. Transparent January 2026 coverage reporting.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.clients.elexon_client import ElexonClient
from backend.app.core.timezone import (
    UTC_TZ,
    ensure_utc,
    get_delivery_date_for_interval,
    calculate_settlement_period,
    format_utc_iso,
    get_delivery_day_bounds_utc,
)
from backend.app.models.actual import ActualGeneration
from backend.app.models.forecast import ForecastGeneration
from backend.app.models.audit import IngestionLog
from backend.app.schemas.elexon import FuelhhWindRecord, WindforForecastRecord
from backend.app.schemas.ingestion import IngestionResultSchema, CoverageReportSchema

logger = logging.getLogger(__name__)


class IngestionService:
    """Service orchestrating data acquisition from Elexon BMRS into SQLite."""

    def __init__(self, db: AsyncSession, client: Optional[ElexonClient] = None):
        self.db = db
        self.client = client or ElexonClient()

    async def ingest_actual_wind_records(
        self,
        records: List[FuelhhWindRecord]
    ) -> IngestionResultSchema:
        """Persist a list of validated FuelhhWindRecord items into actual_generation idempotently."""
        now_utc = datetime.now(timezone.utc)
        if not records:
            return IngestionResultSchema(
                dataset="FUELHH",
                records_retrieved=0,
                records_inserted=0,
                records_skipped_duplicate=0,
                records_rejected_invalid=0,
                status="SUCCESS",
                executed_at=format_utc_iso(now_utc)
            )

        # Get delivery bounds of the batch to query existing records
        min_delivery = min(r.start_time for r in records)
        max_delivery = max(r.start_time for r in records)

        existing_stmt = select(ActualGeneration.delivery_timestamp).where(
            and_(
                ActualGeneration.delivery_timestamp >= min_delivery,
                ActualGeneration.delivery_timestamp <= max_delivery,
                ActualGeneration.source == "ELEXON_FUELHH"
            )
        )
        result = await self.db.execute(existing_stmt)
        existing_timestamps = set(ensure_utc(row[0]) for row in result.all())

        new_entities = []
        skipped_count = 0

        for r in records:
            utc_start = ensure_utc(r.start_time)
            if utc_start in existing_timestamps:
                skipped_count += 1
                continue

            delivery_d = r.settlement_date or get_delivery_date_for_interval(utc_start)
            sp = r.settlement_period or calculate_settlement_period(utc_start)

            entity = ActualGeneration(
                delivery_timestamp=utc_start,
                delivery_date=delivery_d,
                settlement_period=sp,
                generation_mw=r.generation_mw,
                fuel_type=r.fuel_type,
                source="ELEXON_FUELHH",
                publish_timestamp=ensure_utc(r.publish_time) if r.publish_time else None,
                created_at=now_utc
            )
            new_entities.append(entity)
            existing_timestamps.add(utc_start)

        if new_entities:
            self.db.add_all(new_entities)

        # Record audit log
        log_entry = IngestionLog(
            dataset="FUELHH",
            date_from=min_delivery,
            date_to=max_delivery,
            records_retrieved=len(records),
            records_inserted=len(new_entities),
            records_skipped_duplicate=skipped_count,
            records_rejected_invalid=0,
            status="SUCCESS",
            created_at=now_utc
        )
        self.db.add(log_entry)
        await self.db.commit()

        return IngestionResultSchema(
            dataset="FUELHH",
            date_from=format_utc_iso(min_delivery),
            date_to=format_utc_iso(max_delivery),
            records_retrieved=len(records),
            records_inserted=len(new_entities),
            records_skipped_duplicate=skipped_count,
            records_rejected_invalid=0,
            status="SUCCESS",
            executed_at=format_utc_iso(now_utc)
        )

    async def ingest_forecast_records(
        self,
        records: List[WindforForecastRecord]
    ) -> IngestionResultSchema:
        """Persist a list of validated WindforForecastRecord items into forecast_generation idempotently.
        
        Preserves multiple publication vintages for the same delivery interval.
        """
        now_utc = datetime.now(timezone.utc)
        if not records:
            return IngestionResultSchema(
                dataset="WINDFOR",
                records_retrieved=0,
                records_inserted=0,
                records_skipped_duplicate=0,
                records_rejected_invalid=0,
                status="SUCCESS",
                executed_at=format_utc_iso(now_utc)
            )

        min_deliv = min(r.start_time for r in records)
        max_deliv = max(r.start_time for r in records)

        existing_stmt = select(
            ForecastGeneration.delivery_timestamp,
            ForecastGeneration.publish_timestamp
        ).where(
            and_(
                ForecastGeneration.delivery_timestamp >= min_deliv,
                ForecastGeneration.delivery_timestamp <= max_deliv,
                ForecastGeneration.source == "ELEXON_WINDFOR"
            )
        )
        result = await self.db.execute(existing_stmt)
        existing_keys = set((ensure_utc(row[0]), ensure_utc(row[1])) for row in result.all())

        new_entities = []
        skipped_count = 0

        for r in records:
            deliv_utc = ensure_utc(r.start_time)
            pub_utc = ensure_utc(r.publish_time)
            key = (deliv_utc, pub_utc)

            if key in existing_keys:
                skipped_count += 1
                continue

            delivery_d = get_delivery_date_for_interval(deliv_utc)

            entity = ForecastGeneration(
                delivery_timestamp=deliv_utc,
                delivery_date=delivery_d,
                publish_timestamp=pub_utc,
                generation_mw=r.generation_mw,
                source="ELEXON_WINDFOR",
                lead_time_hours=r.lead_time_hours,
                is_ex_ante=r.is_ex_ante,
                created_at=now_utc
            )
            new_entities.append(entity)
            existing_keys.add(key)

        if new_entities:
            self.db.add_all(new_entities)

        log_entry = IngestionLog(
            dataset="WINDFOR",
            date_from=min_deliv,
            date_to=max_deliv,
            records_retrieved=len(records),
            records_inserted=len(new_entities),
            records_skipped_duplicate=skipped_count,
            records_rejected_invalid=0,
            status="SUCCESS",
            created_at=now_utc
        )
        self.db.add(log_entry)
        await self.db.commit()

        return IngestionResultSchema(
            dataset="WINDFOR",
            date_from=format_utc_iso(min_deliv),
            date_to=format_utc_iso(max_deliv),
            records_retrieved=len(records),
            records_inserted=len(new_entities),
            records_skipped_duplicate=skipped_count,
            records_rejected_invalid=0,
            status="SUCCESS",
            executed_at=format_utc_iso(now_utc)
        )

    async def ingest_january_2026(
        self,
        chunk_days: int = 3
    ) -> Tuple[IngestionResultSchema, IngestionResultSchema]:
        """Orchestrate end-to-end ingestion of FUELHH and WINDFOR for January 2026.
        
        1. Ingests FUELHH actuals from 2026-01-01 through 2026-01-31 (1,488 half-hour SPs).
        2. Ingests WINDFOR forecasts published between 2025-12-30T00:00:00Z and 2026-01-31T23:59:59Z,
           filtering delivery start times to [2026-01-01T00:00:00Z, 2026-02-01T00:00:00Z).
        """
        start_d = date(2026, 1, 1)
        end_d = date(2026, 1, 31)

        # 1. Actuals
        logger.info("Starting January 2026 actual wind generation ingestion...")
        actual_records = await self.client.fetch_actual_wind_generation(
            settlement_date_from=start_d,
            settlement_date_to=end_d,
            chunk_days=chunk_days
        )
        actual_res = await self.ingest_actual_wind_records(actual_records)
        logger.info(f"Actuals ingestion finished: {actual_res.records_inserted} inserted, {actual_res.records_skipped_duplicate} skipped.")

        # 2. Forecasts
        logger.info("Starting January 2026 wind forecasts ingestion...")
        pub_from = datetime(2025, 12, 30, 0, 0, 0, tzinfo=UTC_TZ)
        pub_to = datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC_TZ)
        deliv_start, _ = get_delivery_day_bounds_utc(start_d)
        _, deliv_end = get_delivery_day_bounds_utc(end_d)

        forecast_records = await self.client.fetch_wind_forecasts(
            publish_time_from=pub_from,
            publish_time_to=pub_to,
            target_delivery_start=deliv_start,
            target_delivery_end=deliv_end,
            chunk_days=chunk_days
        )
        forecast_res = await self.ingest_forecast_records(forecast_records)
        logger.info(f"Forecasts ingestion finished: {forecast_res.records_inserted} inserted, {forecast_res.records_skipped_duplicate} skipped.")

        return actual_res, forecast_res

    async def get_january_coverage_report(self) -> CoverageReportSchema:
        """Calculate exact January 2026 data coverage metrics from database records."""
        start_d = date(2026, 1, 1)
        end_d = date(2026, 1, 31)
        expected_actuals = 31 * 48  # 1,488
        expected_hourly_forecasts = 31 * 24  # 744

        # Actuals count in January 2026
        act_stmt = select(func.count(func.distinct(ActualGeneration.delivery_timestamp))).where(
            and_(
                ActualGeneration.delivery_date >= start_d,
                ActualGeneration.delivery_date <= end_d
            )
        )
        act_res = await self.db.execute(act_stmt)
        stored_actuals = act_res.scalar() or 0
        missing_actuals = max(0, expected_actuals - stored_actuals)
        act_pct = round((stored_actuals / expected_actuals) * 100.0, 2) if expected_actuals > 0 else 0.0

        # Forecasts total records count (all vintages) in January 2026
        fc_vintages_stmt = select(func.count(ForecastGeneration.id)).where(
            and_(
                ForecastGeneration.delivery_date >= start_d,
                ForecastGeneration.delivery_date <= end_d
            )
        )
        fc_vintages_res = await self.db.execute(fc_vintages_stmt)
        stored_fc_vintages = fc_vintages_res.scalar() or 0

        # Forecasts distinct delivery intervals in January 2026
        fc_intervals_stmt = select(func.count(func.distinct(ForecastGeneration.delivery_timestamp))).where(
            and_(
                ForecastGeneration.delivery_date >= start_d,
                ForecastGeneration.delivery_date <= end_d
            )
        )
        fc_intervals_res = await self.db.execute(fc_intervals_stmt)
        unique_fc_intervals = fc_intervals_res.scalar() or 0
        missing_fc_intervals = max(0, expected_hourly_forecasts - unique_fc_intervals)
        fc_pct = round((unique_fc_intervals / expected_hourly_forecasts) * 100.0, 2) if expected_hourly_forecasts > 0 else 0.0

        # Cumulative audit counters from IngestionLog
        audit_stmt = select(
            func.sum(IngestionLog.records_skipped_duplicate),
            func.sum(IngestionLog.records_rejected_invalid)
        )
        audit_res = await self.db.execute(audit_stmt)
        audit_row = audit_res.first()
        skipped_total = int(audit_row[0] or 0) if audit_row else 0
        rejected_total = int(audit_row[1] or 0) if audit_row else 0

        return CoverageReportSchema(
            target_period="2026-01-01 to 2026-01-31",
            expected_actual_intervals=expected_actuals,
            stored_actual_intervals=stored_actuals,
            missing_actual_intervals=missing_actuals,
            actual_coverage_percent=act_pct,
            expected_hourly_forecast_intervals=expected_hourly_forecasts,
            stored_forecast_vintages_count=stored_fc_vintages,
            unique_forecast_delivery_intervals=unique_fc_intervals,
            missing_forecast_delivery_intervals=missing_fc_intervals,
            forecast_interval_coverage_percent=fc_pct,
            duplicates_skipped_total=skipped_total,
            invalid_records_rejected_total=rejected_total
        )
