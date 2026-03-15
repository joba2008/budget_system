"""Budget submission status model — SQLAlchemy ORM."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint

from config.database import Base


class BudgetSubmissionStatus(Base):
    """Department budget submission status tracking."""
    __tablename__ = 'bsa_submission_status'

    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('editing', 'Editing'),
        ('under_review', 'Under Review'),
        ('complete', 'Complete'),
    ]

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), index=True, nullable=False)
    dept_ppt = Column(String(300), index=True, nullable=False)
    status = Column(String(20), default='not_started', nullable=False)
    submitted_by = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('version', 'dept_ppt', name='uq_submission_version_dept'),
    )

    def __repr__(self):
        return f'<BudgetSubmissionStatus {self.version} | {self.dept_ppt} - {self.status}>'
