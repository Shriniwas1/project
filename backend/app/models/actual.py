from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, Date, UniqueConstraint, Index
from backend.app.core.database import Base, UTCDateTime


class ActualGeneration(Base):
    """SQLAlchemy model for verified UK national wind outturn generation from Elexon FUELHH.
    
    Physical Resolution: Native 30-minute GB settlement periods (SP 1 to 48/50).
    """
    __tablename__ = "actual_generation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_timestamp = Column(UTCDateTime, nullable=False, index=True)
    delivery_date = Column(Date, nullable=False, index=True)
    settlement_period = Column(Integer, nullable=False)
    generation_mw = Column(Float, nullable=False)
    fuel_type = Column(String(16), nullable=False, default="WIND")
    source = Column(String(32), nullable=False, default="ELEXON_FUELHH")
    publish_timestamp = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("delivery_timestamp", "source", name="uq_actual_delivery_source"),
        Index("ix_actual_date_sp", "delivery_date", "settlement_period"),
    )

    def __repr__(self) -> str:
        return (
            f"<ActualGeneration(id={self.id}, delivery={self.delivery_timestamp}, "
            f"SP={self.settlement_period}, mw={self.generation_mw})>"
        )
