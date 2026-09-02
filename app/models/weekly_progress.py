from datetime import datetime
from app.extensions import db


class WeeklyProgress(db.Model):
    """
    Weekly progress tracking model for IITM subjects.
    
    Tracks completion status on a week-by-week basis (Week 1, Week 2, etc.)
    with a status of 'Not Started', 'In Progress', or 'Completed'.
    """
    __tablename__ = 'weekly_progress'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey('subjects.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    week_number = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Not Started',
        server_default='Not Started'
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        server_default=db.func.now(),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=db.func.now(),
        nullable=False
    )

    # Enforce uniqueness of week_number per subject
    __table_args__ = (
        db.UniqueConstraint('subject_id', 'week_number', name='uq_subject_week_number'),
    )

    def __repr__(self):
        return f'<WeeklyProgress Subject={self.subject_id} Week={self.week_number} Status={self.status}>'
