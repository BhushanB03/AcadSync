import os
from flask import Flask, flash, redirect, request, url_for
from app.config import Config
from app.extensions import db, migrate, login_manager, csrf


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
    )
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import User model here to avoid circular imports
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Ensure uploads directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    @app.errorhandler(413)
    def handle_request_entity_too_large(error):
        flash('Uploaded file exceeds the 16 MB limit.', 'error')
        return redirect(request.referrer or url_for('subjects.index'))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.subjects import subjects_bp
    from app.routes.grades import grades_bp
    from app.routes.materials import materials_bp
    from app.routes.tasks import tasks_bp
    from app.routes.progress import progress_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(progress_bp)

    return app