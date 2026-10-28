"""Pydantic schemas for data ingestion results and January 2026 coverage audits."""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class IngestionResultSchema(BaseModel):
    """Result of an ingestion run for a dataset."""
    
    dataset: str = Field(..., description="Ingested dataset identifier ('FUELHH' or 'WINDFOR')")
    date_from: Optional[str] = Field(None, description="Start boundary queried")
    date_to: Optional[str] = Field(None, description="End boundary queried")
    records_retrieved: int = Field(0, description="Total records returned by API")
    records_inserted: int = Field(0, description="New records inserted into database")
    records_skipped_duplicate: int = Field(0, description="Duplicate records skipped")
    records_rejected_invalid: int = Field(0, description="Invalid or malformed records rejected")
    status: str = Field("SUCCESS", description="Execution status: SUCCESS, PARTIAL, or FAILED")
    error_message: Optional[str] = Field(None, description="Error detail if status is FAILED")
    executed_at: str = Field(..., description="UTC timestamp of completion")


class CoverageReportSchema(BaseModel):
    """Rigorous audit of January 2026 actual and forecast data coverage."""
    
    target_period: str = Field("2026-01-01 to 2026-01-31", description="Evaluation delivery date window")
    
    # Actual Outturn (30-min settlement intervals)
    expected_actual_intervals: int = Field(1488, description="Expected 30-min settlement periods (31 days * 48 SP)")
    stored_actual_intervals: int = Field(0, description="Distinct actual generation intervals stored in DB")
    missing_actual_intervals: int = Field(0, description="Expected actual intervals missing from DB")
    actual_coverage_percent: float = Field(0.0, description="Percentage of expected actual intervals stored")
    
    # Wind Forecasts (1-hour resolution)
    expected_hourly_forecast_intervals: int = Field(744, description="Expected hourly delivery intervals (31 days * 24 hours)")
    stored_forecast_vintages_count: int = Field(0, description="Total forecast records stored across all vintages")
    unique_forecast_delivery_intervals: int = Field(0, description="Distinct hourly delivery intervals with at least one forecast")
    missing_forecast_delivery_intervals: int = Field(0, description="Expected hourly intervals with zero forecasts")
    forecast_interval_coverage_percent: float = Field(0.0, description="Percentage of unique hourly delivery intervals covered")
    
    # Summary & Invariants
    resolutions: Dict[str, str] = Field(
        default={
            "actuals": "30-minute settlement periods (48/day)",
            "forecasts": "1-hour intervals (24/day)"
        },
        description="Dataset native physical resolutions"
    )
    duplicates_skipped_total: int = Field(0, description="Cumulative duplicate records skipped")
    invalid_records_rejected_total: int = Field(0, description="Cumulative malformed records rejected")
