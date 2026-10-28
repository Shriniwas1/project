from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text
from backend.app.core.database import Base, UTCDateTime


class IngestionLog(Base):
    """Audit log tracking API ingestion runs, counts, status, and anomalies."""
    __tablename__ = "ingestion_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset = Column(String(32), nullable=False, index=True)
    date_from = Column(UTCDateTime, nullable=True)
    date_to = Column(UTCDateTime, nullable=True)
    records_retrieved = Column(Integer, nullable=False, default=0)
    records_inserted = Column(Integer, nullable=False, default=0)
    records_skipped_duplicate = Column(Integer, nullable=False, default=0)
    records_rejected_invalid = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="SUCCESS")
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return (
            f"<IngestionLog(id={self.id}, dataset={self.dataset}, "
            f"inserted={self.records_inserted}, status={self.status})>"
        )
