from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response payload schema."""
    
    status: str = Field(..., description="Service health status ('healthy' or 'degraded')")
    version: str = Field("1.0.0", description="Application service version")
    environment: str = Field(..., description="Execution environment")
    database_connected: bool = Field(..., description="Whether database connection succeeded")
    timestamp_utc: str = Field(..., description="Current UTC timestamp")
    dataset_scope: str = Field("January 2026 UK Wind Procurement", description="Evaluation dataset scope")
    actual_records_count: int = Field(0, description="Count of actual wind generation records in DB")
    forecast_records_count: int = Field(0, description="Count of forecast records in DB")
    default_decision_cutoff: str = Field("11:00 Europe/London", description="Assumed Day-Ahead decision cutoff")
