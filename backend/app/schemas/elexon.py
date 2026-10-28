"""Pydantic validation schemas for raw and validated Elexon BMRS datasets."""

from datetime import date, datetime
from typing import Optional, Union, Any
from pydantic import BaseModel, Field, field_validator, computed_field
from backend.app.core.timezone import ensure_utc, parse_iso_to_utc


class FuelhhWindRecord(BaseModel):
    """Validated model for actual wind generation from FUELHH dataset.
    
    Fields:
    - start_time: Start of the 30-min settlement delivery interval (UTC).
    - settlement_date: GB market calendar settlement date (Europe/London).
    - settlement_period: GB Settlement period integer (1 to 48/50).
    - generation_mw: Actual active wind power delivered to transmission grid (MW).
    - fuel_type: Fuel category, strictly 'WIND'.
    - publish_time: Elexon settlement run publication timestamp (UTC).
    """
    
    start_time: datetime = Field(..., description="UTC start of the 30-min settlement delivery interval")
    settlement_date: date = Field(..., description="Calendar settlement date in Great Britain")
    settlement_period: int = Field(..., ge=1, le=50, description="Settlement period number (1-50)")
    generation_mw: float = Field(..., ge=0.0, description="Actual wind power outturn in MW")
    fuel_type: str = Field("WIND", description="Fuel type category, strictly 'WIND'")
    publish_time: Optional[datetime] = Field(None, description="Settlement publication timestamp in UTC")
    dataset: str = Field("FUELHH", description="Source dataset identifier")

    @field_validator("start_time", "publish_time", mode="before")
    @classmethod
    def validate_timestamps(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            return parse_iso_to_utc(v)
        if isinstance(v, datetime):
            return ensure_utc(v)
        raise ValueError(f"Invalid timestamp value: {v}")

    @field_validator("generation_mw", mode="before")
    @classmethod
    def validate_generation(cls, v: Any) -> float:
        if v is None:
            raise ValueError("Generation value cannot be null")
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"Generation value must be numeric, got {v}")
        if val < 0:
            raise ValueError(f"Generation outturn cannot be negative: {val}")
        return val


class WindforForecastRecord(BaseModel):
    """Validated model for forecast wind generation from WINDFOR dataset.
    
    Dual Timestamps:
    - start_time: Target delivery interval start timestamp in UTC.
    - publish_time: Timestamp when NESO generated and published this forecast vintage in UTC.
    
    Domain Rules:
    - Both timestamps are preserved independently without mutation or overwriting.
    - Ex-ante forecasts have publish_time <= start_time (lead_time_hours >= 0).
    - Ex-post / retrospective records have publish_time > start_time (lead_time_hours < 0).
      These retrospective records represent historical anchor periods included in NESO's
      72-hour sliding window batch runs. They are NOT eligible as day-ahead forecasts.
    """
    
    start_time: datetime = Field(..., description="UTC start of the target delivery interval")
    publish_time: datetime = Field(..., description="UTC timestamp when the forecast vintage was published")
    generation_mw: float = Field(..., ge=0.0, description="Forecasted wind generation in MW")
    dataset: str = Field("WINDFOR", description="Source dataset identifier")

    @field_validator("start_time", "publish_time", mode="before")
    @classmethod
    def validate_timestamps(cls, v: Any) -> datetime:
        if v is None:
            raise ValueError("Timestamp cannot be null")
        if isinstance(v, str):
            return parse_iso_to_utc(v)
        if isinstance(v, datetime):
            return ensure_utc(v)
        raise ValueError(f"Invalid timestamp value: {v}")

    @field_validator("generation_mw", mode="before")
    @classmethod
    def validate_generation(cls, v: Any) -> float:
        if v is None:
            raise ValueError("Generation value cannot be null")
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"Generation value must be numeric, got {v}")
        if val < 0:
            raise ValueError(f"Forecast generation cannot be negative: {val}")
        return val

    @computed_field
    @property
    def lead_time_hours(self) -> float:
        """Lead time in hours between publication and delivery start.
        
        Positive: Published before delivery (ex-ante).
        Negative: Published after delivery (ex-post / retrospective).
        """
        diff_seconds = (self.start_time - self.publish_time).total_seconds()
        return round(diff_seconds / 3600.0, 2)

    @computed_field
    @property
    def is_ex_ante(self) -> bool:
        """Whether this forecast was published at or before physical delivery start."""
        return self.publish_time <= self.start_time
