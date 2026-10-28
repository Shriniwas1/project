from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, Date, Boolean, UniqueConstraint, Index
from backend.app.core.database import Base, UTCDateTime


class ForecastGeneration(Base):
    """SQLAlchemy model for UK national wind generation forecasts from Elexon WINDFOR.
    
    Physical Resolution: Native 1-hour intervals (:00 timestamps).
    Multi-Vintage Support: Multiple publication revisions are preserved for each delivery interval.
    """
    __tablename__ = "forecast_generation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_timestamp = Column(UTCDateTime, nullable=False, index=True)
    delivery_date = Column(Date, nullable=False, index=True)
    publish_timestamp = Column(UTCDateTime, nullable=False, index=True)
    generation_mw = Column(Float, nullable=False)
    source = Column(String(32), nullable=False, default="ELEXON_WINDFOR")
    lead_time_hours = Column(Float, nullable=True)
    is_ex_ante = Column(Boolean, nullable=False, default=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint(
            "delivery_timestamp",
            "publish_timestamp",
            "source",
            name="uq_forecast_delivery_publish_source"
        ),
        Index("ix_forecast_date_pub", "delivery_date", "publish_timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<ForecastGeneration(id={self.id}, delivery={self.delivery_timestamp}, "
            f"publish={self.publish_timestamp}, mw={self.generation_mw}, ex_ante={self.is_ex_ante})>"
        )
