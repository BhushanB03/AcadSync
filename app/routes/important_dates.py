from datetime import date
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.important_date import ImportantDate
from app.models.subject import Subject

important_dates_bp = Blueprint('important_dates', __name__, url_prefix='/important-dates')

VALID_UNIVERSITIES = ['All', 'VIT', 'IITM']


def _get_user_subjects():
    """Return all subjects owned by the current user ordered by university and name."""
    return Subject.query.filter_by(user_id=current_user.id).order_by(
        Subject.university.asc(),
        Subject.name.asc()
    ).all()


@important_dates_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    List all of current_user's important dates.
    Supports filtering by university (All/VIT/IITM) via query parameter.
    Dates are sorted chronologically ascending.
    """
    university_filter = request.args.get('university', 'All')
    if university_filter not in VALID_UNIVERSITIES:
        university_filter = 'All'

    query = ImportantDate.query.filter_by(user_id=current_user.id)

    if university_filter != 'All':
        query = query.filter_by(university=university_filter)

    query = query.order_by(ImportantDate.date.asc(), ImportantDate.created_at.desc())
    dates = query.all()

    return render_template(
        'important_dates/list.html',
        dates=dates,
        selected_university=university_filter,
        today=date.today()
    )


@important_dates_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    Create a new important date reminder for the current user.
    Validates that optional subject_id belongs to current_user and matches the chosen university.
    """
    subjects = _get_user_subjects()
    preselected_uni = request.args.get('university', 'IITM')
    if preselected_uni not in ['VIT', 'IITM']:
        preselected_uni = 'IITM'

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        university = request.form.get('university', '').strip()
        subject_id_raw = request.form.get('subject_id', '').strip()
        date_raw = request.form.get('date', '').strip()
        note = request.form.get('note', '').strip() or None

        # 1. Title validation
        if not title:
            flash('Title is required.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=None,
                subjects=subjects,
                selected_university=university or preselected_uni
            )

        # 2. University validation
        if university not in ['VIT', 'IITM']:
            flash('Please select a valid university (VIT or IITM).', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=None,
                subjects=subjects,
                selected_university=preselected_uni
            )

        # 3. Date validation
        if not date_raw:
            flash('Date is required.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=None,
                subjects=subjects,
                selected_university=university
            )

        try:
            date_val = date.fromisoformat(date_raw)
        except ValueError:
            flash('Please enter a valid date in YYYY-MM-DD format.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=None,
                subjects=subjects,
                selected_university=university
            )

        # 4. Optional Subject validation & university cross-check
        subject_id = None
        if subject_id_raw:
            try:
                subject_id = int(subject_id_raw)
            except ValueError:
                flash('The selected subject is invalid.', 'error')
                return render_template(
                    'important_dates/form.html',
                    date_item=None,
                    subjects=subjects,
                    selected_university=university
                )

            subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
            if not subject:
                flash('The selected subject does not belong to your account.', 'error')
                return render_template(
                    'important_dates/form.html',
                    date_item=None,
                    subjects=subjects,
                    selected_university=university
                )

            if subject.university != university:
                flash(
                    f'Mismatch: Selected subject "{subject.name}" belongs to {subject.university}, '
                    f'but the reminder university is set to {university}. Please select a matching subject.',
                    'error'
                )
                return render_template(
                    'important_dates/form.html',
                    date_item=None,
                    subjects=subjects,
                    selected_university=university
                )

        important_date = ImportantDate(
            user_id=current_user.id,
            university=university,
            subject_id=subject_id,
            title=title,
            date=date_val,
            note=note
        )

        try:
            db.session.add(important_date)
            db.session.commit()
            flash(f'Important date "{title}" added successfully!', 'success')
            return redirect(url_for('important_dates.index', university=university))
        except Exception:
            db.session.rollback()
            flash('An error occurred while saving the important date. Please try again.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=None,
                subjects=subjects,
                selected_university=university
            )

    return render_template(
        'important_dates/form.html',
        date_item=None,
        subjects=subjects,
        selected_university=preselected_uni
    )


@important_dates_bp.route('/<int:date_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(date_id):
    """
    Edit an existing important date after verifying ownership.
    Ensures that updated subject belongs to current user and matches the selected university.
    """
    date_item = ImportantDate.query.get_or_404(date_id)
    if date_item.user_id != current_user.id:
        abort(403)

    subjects = _get_user_subjects()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        university = request.form.get('university', '').strip()
        subject_id_raw = request.form.get('subject_id', '').strip()
        date_raw = request.form.get('date', '').strip()
        note = request.form.get('note', '').strip() or None

        if not title:
            flash('Title is required.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=date_item,
                subjects=subjects,
                selected_university=date_item.university
            )

        if university not in ['VIT', 'IITM']:
            flash('Please select a valid university (VIT or IITM).', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=date_item,
                subjects=subjects,
                selected_university=date_item.university
            )

        if not date_raw:
            flash('Date is required.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=date_item,
                subjects=subjects,
                selected_university=university
            )

        try:
            date_val = date.fromisoformat(date_raw)
        except ValueError:
            flash('Please enter a valid date in YYYY-MM-DD format.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=date_item,
                subjects=subjects,
                selected_university=university
            )

        subject_id = None
        if subject_id_raw:
            try:
                subject_id = int(subject_id_raw)
            except ValueError:
                flash('The selected subject is invalid.', 'error')
                return render_template(
                    'important_dates/form.html',
                    date_item=date_item,
                    subjects=subjects,
                    selected_university=university
                )

            subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
            if not subject:
                flash('The selected subject does not belong to your account.', 'error')
                return render_template(
                    'important_dates/form.html',
                    date_item=date_item,
                    subjects=subjects,
                    selected_university=university
                )

            if subject.university != university:
                flash(
                    f'Mismatch: Selected subject "{subject.name}" belongs to {subject.university}, '
                    f'but the reminder university is set to {university}. Please select a matching subject.',
                    'error'
                )
                return render_template(
                    'important_dates/form.html',
                    date_item=date_item,
                    subjects=subjects,
                    selected_university=university
                )

        date_item.title = title
        date_item.university = university
        date_item.subject_id = subject_id
        date_item.date = date_val
        date_item.note = note

        try:
            db.session.commit()
            flash(f'Important date "{title}" updated successfully!', 'success')
            return redirect(url_for('important_dates.index', university=university))
        except Exception:
            db.session.rollback()
            flash('An error occurred while updating the important date. Please try again.', 'error')
            return render_template(
                'important_dates/form.html',
                date_item=date_item,
                subjects=subjects,
                selected_university=university
            )

    return render_template(
        'important_dates/form.html',
        date_item=date_item,
        subjects=subjects,
        selected_university=date_item.university
    )


@important_dates_bp.route('/<int:date_id>/delete', methods=['POST'])
@login_required
def delete(date_id):
    """
    Delete an important date reminder after verifying ownership.
    """
    date_item = ImportantDate.query.get_or_404(date_id)
    if date_item.user_id != current_user.id:
        abort(403)

    title = date_item.title
    uni = date_item.university

    try:
        db.session.delete(date_item)
        db.session.commit()
        flash(f'Important date "{title}" deleted successfully!', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred while deleting the important date. Please try again.', 'error')

    return redirect(url_for('important_dates.index', university=uni))
