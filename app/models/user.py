from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(UserMixin, db.Model):
    """
    User model with authentication fields and methods.
    Inherits from UserMixin to integrate with Flask-Login (provides id, is_active, etc.)
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to tasks for the unified task list.
    tasks = db.relationship(
        'Task',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        """
        Hash and store the password using werkzeug.security.
        Uses PBKDF2 by default with SHA-256.
        
        Args:
            password (str): Plain text password from user input
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verify a plain text password against the stored hash.
        
        Args:
            password (str): Plain text password from user input
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)
