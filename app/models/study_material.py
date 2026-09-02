from datetime import datetime

from app.extensions import db


class StudyMaterial(db.Model):
    """
    Study materials for a subject grouped by category.

    Each material can be one of three types:
    - file: uploaded document or media file
    - link: external URL
    - note: plain text note content
    """
    __tablename__ = 'study_materials'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False)  # 'lecture_notes' or 'exam_papers'
    material_type = db.Column(db.String(20), nullable=False)  # 'file', 'link', 'note'
    title = db.Column(db.String(200), nullable=False)

    # File-type fields
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)

    # Link-type field
    url = db.Column(db.String(500), nullable=True)

    # Note-type field
    note_content = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<StudyMaterial {self.id}: {self.title}>'
