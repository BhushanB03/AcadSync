from datetime import datetime

from app.extensions import db


class Task(db.Model):
    """
    Task model for the unified user task list.

    A task belongs to a user and may optionally be linked to a subject.
    Tasks are not limited to one university or subject, so they can represent
    university-wide, cross-subject, or standalone work items.
    """
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey('subjects.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(20), nullable=False, default='Medium')
    status = db.Column(db.String(20), nullable=False, default='Not Started')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'
