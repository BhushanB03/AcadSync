from app.extensions import db
from datetime import datetime


class Subject(db.Model):
    """
    Subject model representing an academic subject/course.
    Each subject belongs to a user and stores university preference (VIT or IITM).
    """
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    university = db.Column(db.String(10), nullable=False, default='VIT')  # 'VIT' or 'IITM'
    term = db.Column(db.String(100), nullable=False)  # e.g., "January 2027"
    subject_type = db.Column(db.String(50), nullable=False)  # e.g., "Theory", "Lab"
    status = db.Column(db.String(20), nullable=False, default='Active')  # 'Active', 'Completed', 'Archived'
    formula_text = db.Column(db.Text, nullable=True)  # Grade formula (e.g., "0.05*GLA + max(0.6*F, ...)")
    calculation_mode = db.Column(db.String(20), nullable=False, default='raw')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to User
    user = db.relationship('User', backref='subjects', lazy=True)

    # Tasks linked to this subject. If the subject is deleted, the linked tasks
    # should retain their value by clearing the subject_id instead of being deleted.
    tasks = db.relationship(
        'Task',
        backref='subject',
        lazy=True,
        passive_deletes=True
    )
    
    # Relationships for grade components and boundaries
    components = db.relationship(
        'SubjectComponent',
        backref='subject',
        lazy=True,
        cascade='all, delete-orphan'
    )
    grade_boundaries = db.relationship(
        'SubjectGradeBoundary',
        backref='subject',
        lazy=True,
        cascade='all, delete-orphan'
    )
    study_materials = db.relationship(
        'StudyMaterial',
        backref='subject',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Subject {self.code} - {self.name}>'

    def belongs_to_user(self, user_id):
        """
        Verify that this subject belongs to the given user.
        Useful for ownership checks before edit/delete operations.
        
        Args:
            user_id (int): The user ID to check against
            
        Returns:
            bool: True if subject belongs to user, False otherwise
        """
        return self.user_id == user_id
