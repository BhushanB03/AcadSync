from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.subject import Subject
from app.models.task import Task


tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

VALID_STATUSES = ['All', 'Not Started', 'In Progress', 'Completed']
VALID_PRIORITIES = ['All', 'High', 'Medium', 'Low']
VALID_UNIVERSITIES = ['All', 'VIT', 'IITM']
VALID_SORTS = ['due_date', 'priority']


def _get_subject_options():
    """Return the current user's subjects in a consistent order."""
    return Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name.asc()).all()


def _get_priority_order():
    """Return a SQLAlchemy case expression used for sorting tasks by priority."""
    return db.case(
        (Task.priority == 'High', 3),
        (Task.priority == 'Medium', 2),
        (Task.priority == 'Low', 1),
        else_=0
    )


@tasks_bp.route('/', methods=['GET'])
@login_required
def index():
    """Display the current user's unified task list with optional filtering."""
    status_filter = request.args.get('status', 'All')
    priority_filter = request.args.get('priority', 'All')
    subject_filter = request.args.get('subject_id', 'All')
    university_filter = request.args.get('university', 'All')
    sort = request.args.get('sort', 'due_date')

    if status_filter not in VALID_STATUSES:
        status_filter = 'All'
    if priority_filter not in VALID_PRIORITIES:
        priority_filter = 'All'
    if university_filter not in VALID_UNIVERSITIES:
        university_filter = 'All'
    if sort not in VALID_SORTS:
        sort = 'due_date'

    query = Task.query.filter_by(user_id=current_user.id)

    # Apply status and priority filters first; these do not depend on joins.
    if status_filter != 'All':
        query = query.filter_by(status=status_filter)

    if priority_filter != 'All':
        query = query.filter_by(priority=priority_filter)

    # Apply subject_id filter next. This works with the university join below
    # because both filters act on the same Task rows.
    if subject_filter != 'All':
        try:
            subject_id = int(subject_filter)
        except (TypeError, ValueError):
            subject_id = None

        if subject_id is not None:
            query = query.filter_by(subject_id=subject_id)

    # University filter only applies when tasks are linked to a subject and the
    # linked subject matches the chosen university. Tasks with no subject should be
    # excluded when a university is explicitly selected, but remain visible when
    # 'All' is chosen.
    if university_filter != 'All':
        query = query.join(Subject, Task.subject_id == Subject.id).filter(
            Task.subject_id.isnot(None),
            Subject.university == university_filter
        )

    if sort == 'priority':
        query = query.order_by(
            _get_priority_order().desc(),
            Task.due_date.is_(None),
            Task.due_date.asc(),
            Task.created_at.desc()
        )
    else:
        query = query.order_by(
            Task.due_date.is_(None),
            Task.due_date.asc(),
            _get_priority_order().desc(),
            Task.created_at.desc()
        )

    tasks = query.all()
    subjects = _get_subject_options()

    return render_template(
        'tasks/tasks-list.html',
        tasks=tasks,
        subjects=subjects,
        selected_status=status_filter,
        selected_priority=priority_filter,
        selected_subject_id=subject_filter if subject_filter != 'All' else None,
        selected_university=university_filter,
        selected_sort=sort,
        today=date.today(),
        timedelta=timedelta,
    )


@tasks_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Create a new task for the current user."""
    subjects = _get_subject_options()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip() or None
        subject_id_raw = request.form.get('subject_id', '').strip()
        due_date_raw = request.form.get('due_date', '').strip()
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Not Started')

        if not title:
            flash('Task title is required.', 'error')
            return render_template('tasks/task-form.html', task=None, subjects=subjects)

        if subject_id_raw:
            try:
                subject_id = int(subject_id_raw)
            except ValueError:
                flash('The selected subject is invalid.', 'error')
                return render_template('tasks/task-form.html', task=None, subjects=subjects)

            subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
            if not subject:
                flash('The selected subject does not belong to your account.', 'error')
                return render_template('tasks/task-form.html', task=None, subjects=subjects)
        else:
            subject_id = None

        if priority not in ['High', 'Medium', 'Low']:
            priority = 'Medium'
        if status not in ['Not Started', 'In Progress', 'Completed']:
            status = 'Not Started'

        due_date = None
        if due_date_raw:
            try:
                due_date = date.fromisoformat(due_date_raw)
            except ValueError:
                flash('Please enter a valid due date in YYYY-MM-DD format.', 'error')
                return render_template('tasks/task-form.html', task=None, subjects=subjects)

        task = Task(
            user_id=current_user.id,
            subject_id=subject_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            status=status,
        )

        try:
            db.session.add(task)
            db.session.commit()
            flash(f'Task "{title}" added successfully!', 'success')
            return redirect(url_for('tasks.index'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while creating the task. Please try again.', 'error')
            return render_template('tasks/task-form.html', task=None, subjects=subjects)

    return render_template('tasks/task-form.html', task=None, subjects=subjects)


@tasks_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    """Edit an existing task after verifying the owner."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    subjects = _get_subject_options()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip() or None
        subject_id_raw = request.form.get('subject_id', '').strip()
        due_date_raw = request.form.get('due_date', '').strip()
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Not Started')

        if not title:
            flash('Task title is required.', 'error')
            return render_template('tasks/task-form.html', task=task, subjects=subjects)

        if subject_id_raw:
            try:
                subject_id = int(subject_id_raw)
            except ValueError:
                flash('The selected subject is invalid.', 'error')
                return render_template('tasks/task-form.html', task=task, subjects=subjects)

            subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
            if not subject:
                flash('The selected subject does not belong to your account.', 'error')
                return render_template('tasks/task-form.html', task=task, subjects=subjects)
        else:
            subject_id = None

        if priority not in ['High', 'Medium', 'Low']:
            priority = 'Medium'
        if status not in ['Not Started', 'In Progress', 'Completed']:
            status = 'Not Started'

        due_date = None
        if due_date_raw:
            try:
                due_date = date.fromisoformat(due_date_raw)
            except ValueError:
                flash('Please enter a valid due date in YYYY-MM-DD format.', 'error')
                return render_template('tasks/task-form.html', task=task, subjects=subjects)

        task.subject_id = subject_id
        task.title = title
        task.description = description
        task.due_date = due_date
        task.priority = priority
        task.status = status

        try:
            db.session.commit()
            flash(f'Task "{title}" updated successfully!', 'success')
            return redirect(url_for('tasks.index'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while updating the task. Please try again.', 'error')
            return render_template('tasks/task-form.html', task=task, subjects=subjects)

    return render_template('tasks/task-form.html', task=task, subjects=subjects)


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete(task_id):
    """Delete a task after verifying the owner."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    task_title = task.title

    try:
        db.session.delete(task)
        db.session.commit()
        flash(f'Task "{task_title}" deleted successfully!', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred while deleting the task. Please try again.', 'error')

    return redirect(url_for('tasks.index'))

@tasks_bp.route('/<int:task_id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(task_id):
    """Cycle the task status without opening the full edit form."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    if task.status == 'Not Started':
        task.status = 'In Progress'
    elif task.status == 'In Progress':
        task.status = 'Completed'
    else:
        task.status = 'Not Started'

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Unable to update the task status right now.', 'error')
        return redirect(request.referrer or url_for('tasks.index'))

    return redirect(request.referrer or url_for('tasks.index'))