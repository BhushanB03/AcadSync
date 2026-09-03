"""
Assessment and component models for grade calculation.
Includes template-level and subject-level configurations.
"""

from datetime import datetime
from app.extensions import db


class GradeTemplateComponent(db.Model):
    """
    Represents a component (e.g., GLA, F, Qz1) in a GradeTemplate.
    
    Attributes:
        id: Primary key
        template_id: Foreign key to GradeTemplate
        component_code: Short code for the component (e.g., "GLA", "F"), used in formulas
        component_name: Display name (e.g., "Group Learning Activities")
        max_marks: Maximum marks possible for this component
    """
    
    __tablename__ = 'grade_template_components'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('grade_templates.id'), nullable=False, index=True)
    component_code = db.Column(db.String(50), nullable=False)  # e.g., "GLA", "F", "Qz1"
    component_name = db.Column(db.String(150), nullable=False)  # e.g., "Group Learning Activities"
    max_marks = db.Column(db.Float, nullable=False)  # e.g., 100.0
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def __repr__(self):
        return f"<GradeTemplateComponent {self.component_code} (max: {self.max_marks})>"


class GradeTemplateGradeBoundary(db.Model):
    """
    Represents a grade boundary (e.g., 90-100 -> S) in a GradeTemplate.
    
    Attributes:
        id: Primary key
        template_id: Foreign key to GradeTemplate
        grade_label: Grade letter (e.g., "S", "A", "B", "C", "D", "E", "U")
        min_score: Minimum score (inclusive) for this grade
        max_score: Maximum score (inclusive) for this grade
    """
    
    __tablename__ = 'grade_template_grade_boundaries'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('grade_templates.id'), nullable=False, index=True)
    grade_label = db.Column(db.String(10), nullable=False)  # e.g., "S", "A", "B", "C", "D", "E", "U"
    min_score = db.Column(db.Float, nullable=False)  # e.g., 90.0
    max_score = db.Column(db.Float, nullable=False)  # e.g., 100.0
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def __repr__(self):
        return f"<GradeTemplateGradeBoundary {self.grade_label}: {self.min_score}-{self.max_score}>"


class SubjectComponent(db.Model):
    """
    Represents a component (e.g., GLA, F, Qz1) for a specific Subject.
    Stores both the definition (max_marks) and the obtained marks.
    
    Attributes:
        id: Primary key
        subject_id: Foreign key to Subject
        component_code: Short code for the component (e.g., "GLA", "F"), used in formulas
        component_name: Display name (e.g., "Group Learning Activities")
        max_marks: Maximum marks possible for this component
        obtained_marks: Actual marks obtained (nullable — can be entered later)
    """
    
    __tablename__ = 'subject_components'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    component_code = db.Column(db.String(50), nullable=False)  # e.g., "GLA", "F", "Qz1"
    component_name = db.Column(db.String(150), nullable=False)  # e.g., "Group Learning Activities"
    max_marks = db.Column(db.Float, nullable=False)  # e.g., 100.0
    obtained_marks = db.Column(db.Float, nullable=True)  # e.g., 85.5 (or None if not yet entered)
    
    def get_percentage(self):
        """
        Returns the percentage score (obtained_marks / max_marks) * 100.
        Returns None if obtained_marks is not set.
        """
        if self.obtained_marks is None:
            return None
        return (self.obtained_marks / self.max_marks) * 100.0 if self.max_marks > 0 else 0.0
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def __repr__(self):
        return f"<SubjectComponent {self.component_code}: {self.obtained_marks}/{self.max_marks}>"


class SubjectGradeBoundary(db.Model):
    """
    Represents a grade boundary (e.g., 90-100 -> S) for a specific Subject.
    Allows per-subject customization of grade boundaries.
    
    Attributes:
        id: Primary key
        subject_id: Foreign key to Subject
        grade_label: Grade letter (e.g., "S", "A", "B", "C", "D", "E", "U")
        min_score: Minimum score (inclusive) for this grade
        max_score: Maximum score (inclusive) for this grade
    """
    
    __tablename__ = 'subject_grade_boundaries'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    grade_label = db.Column(db.String(10), nullable=False)  # e.g., "S", "A", "B", "C", "D", "E", "U"
    min_score = db.Column(db.Float, nullable=False)  # e.g., 90.0
    max_score = db.Column(db.Float, nullable=False)  # e.g., 100.0
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def __repr__(self):
        return f"<SubjectGradeBoundary {self.grade_label}: {self.min_score}-{self.max_score}>"
