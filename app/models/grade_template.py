"""
Grade Template model for storing reusable grading formulas and configurations.
Allows users to define a formula once and apply it to multiple subjects.
"""

from datetime import datetime
from app.extensions import db


class GradeTemplate(db.Model):
    """
    Represents a reusable grade calculation template with formula and components.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to User (template owner)
        name: Display name of the template (e.g., "IITM MAD1 Grading")
        university: 'VIT' or 'IITM'
        formula_text: Formula string with component codes (e.g., "0.05*GLA + max(0.6*F, ...)")
        created_at: Timestamp of creation
        
    Relationships:
        user: Backref to User model
        components: List of GradeTemplateComponent objects (cascade delete-orphan)
        grade_boundaries: List of GradeTemplateGradeBoundary objects (cascade delete-orphan)
    """
    
    __tablename__ = 'grade_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    university = db.Column(db.String(10), nullable=False)  # 'VIT' or 'IITM'
    formula_text = db.Column(db.Text, nullable=False)
    calculation_mode = db.Column(db.String(20), nullable=False, default='raw')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='grade_templates', lazy=True)
    components = db.relationship(
        'GradeTemplateComponent',
        backref='template',
        lazy=True,
        cascade='all, delete-orphan'
    )
    grade_boundaries = db.relationship(
        'GradeTemplateGradeBoundary',
        backref='template',
        lazy=True,
        cascade='all, delete-orphan'
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def belongs_to_user(self, user_id):
        """Check if template belongs to the given user."""
        return self.user_id == user_id
    
    def __repr__(self):
        return f"<GradeTemplate {self.id}: {self.name} ({self.university})>"
