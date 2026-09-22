from datetime import date, datetime
from app.extensions import db


class ImportantDate(db.Model):
    """
    ImportantDate model for tracking critical academic reminders and deadlines
    (e.g., exam dates, registration deadlines, fee due dates).

    Each important date is university-specific ('VIT' or 'IITM') and can
    optionally be linked to a specific subject within that university.
    """
    __tablename__ = 'important_dates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    university = db.Column(
        db.String(10),
        nullable=False
    )  # 'VIT' or 'IITM'
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey('subjects.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    title = db.Column(
        db.String(200),
        nullable=False
    )  # e.g. "DWM End Term Exam"
    date = db.Column(
        db.Date,
        nullable=False
    )
    note = db.Column(
        db.Text,
        nullable=True
    )  # Explanation of why this date matters
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<ImportantDate {self.id}: {self.title} ({self.university}) - {self.date}>'

    def belongs_to_user(self, user_id):
        """Verify that this important date belongs to the specified user."""
        return self.user_id == user_id

    @property
    def is_past(self):
        """Check if the date is in the past relative to today."""
        return self.date < date.today()

    @property
    def days_remaining(self):
        """Return the number of days remaining until this date."""
        return (self.date - date.today()).days
