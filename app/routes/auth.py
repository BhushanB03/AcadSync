from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from app.extensions import db
from app.models.user import User
from app.models.subject import Subject
from app.models.task import Task

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handle user registration.
    GET: Display the registration form.
    POST: Create a new user, hash password, save to DB, redirect to login.
    """
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('auth.register'))

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please log in or use a different email.', 'error')
            return redirect(url_for('auth.register'))

        # Create new user
        user = User(name=name, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash(f'Account created successfully! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.
    GET: Display the login form.
    POST: Verify credentials and log the user in using Flask-Login.
    """
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Validation
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('auth.login'))

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Verify password (check_password returns False if user doesn't exist, preventing user enumeration)
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember') is not None)
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect to next page if provided, otherwise to dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):  # Security: only allow relative URLs
                return redirect(next_page)
            return redirect(url_for('auth.dashboard'))
        else:
            # Don't reveal whether email exists (security best practice)
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Log out the current user using Flask-Login's logout_user().
    Requires user to be authenticated (@login_required).
    """
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Unified dual-context dashboard for authenticated users.
    
    Fetches both IITM and VIT subjects, upcoming tasks (including standalone tasks),
    and overdue counts in a single request to enable instant client-side tab switching.
    """
    today = date.today()

    # 1. Active subjects per university
    iitm_subjects = (
        Subject.query
        .filter(
            Subject.user_id == current_user.id,
            Subject.university == 'IITM',
            Subject.status.in_(['Active', 'Completed'])
        )
        .order_by(Subject.created_at.desc())
        .all()
    )

    vit_subjects = (
        Subject.query
        .filter(
            Subject.user_id == current_user.id,
            Subject.university == 'VIT',
            Subject.status.in_(['Active', 'Completed'])
        )
        .order_by(Subject.created_at.desc())
        .all()
    )

    # 2. Upcoming tasks preview (up to 5 per university context; standalone tasks appear in both)
    # Tasks are sorted by due date (tasks with due dates first, ascending), then creation date
    iitm_tasks = (
        Task.query
        .outerjoin(Subject, Task.subject_id == Subject.id)
        .filter(
            Task.user_id == current_user.id,
            Task.status != 'Completed',
            or_(
                Task.subject_id.is_(None),
                Subject.university == 'IITM'
            )
        )
        .order_by(
            Task.due_date.is_(None),
            Task.due_date.asc(),
            Task.created_at.desc()
        )
        .limit(5)
        .all()
    )

    vit_tasks = (
        Task.query
        .outerjoin(Subject, Task.subject_id == Subject.id)
        .filter(
            Task.user_id == current_user.id,
            Task.status != 'Completed',
            or_(
                Task.subject_id.is_(None),
                Subject.university == 'VIT'
            )
        )
        .order_by(
            Task.due_date.is_(None),
            Task.due_date.asc(),
            Task.created_at.desc()
        )
        .limit(5)
        .all()
    )

    # 3. Overdue task counts per university context
    iitm_overdue_count = (
        Task.query
        .outerjoin(Subject, Task.subject_id == Subject.id)
        .filter(
            Task.user_id == current_user.id,
            Task.status != 'Completed',
            Task.due_date.isnot(None),
            Task.due_date < today,
            or_(
                Task.subject_id.is_(None),
                Subject.university == 'IITM'
            )
        )
        .count()
    )

    vit_overdue_count = (
        Task.query
        .outerjoin(Subject, Task.subject_id == Subject.id)
        .filter(
            Task.user_id == current_user.id,
            Task.status != 'Completed',
            Task.due_date.isnot(None),
            Task.due_date < today,
            or_(
                Task.subject_id.is_(None),
                Subject.university == 'VIT'
            )
        )
        .count()
    )

    return render_template(
        'dashboard.html',
        user=current_user,
        iitm_subjects=iitm_subjects,
        vit_subjects=vit_subjects,
        iitm_tasks=iitm_tasks,
        vit_tasks=vit_tasks,
        iitm_overdue_count=iitm_overdue_count,
        vit_overdue_count=vit_overdue_count,
        today=today,
        timedelta=timedelta
    )
