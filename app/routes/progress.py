from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models.subject import Subject
from app.models.weekly_progress import WeeklyProgress

progress_bp = Blueprint('progress', __name__, url_prefix='/progress')

VALID_STATUSES = {'Not Started', 'In Progress', 'Completed'}


@progress_bp.route('/subject/<int:subject_id>', methods=['GET'])
@login_required
def weekly_progress(subject_id):
    """
    Display the weekly progress checklist/timeline for an IITM subject.
    Restricted to the subject owner and IITM subjects only.
    """
    subject = Subject.query.get_or_404(subject_id)

    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)

    # Feature is restricted to IITM subjects only
    if subject.university != 'IITM':
        flash('Weekly progress tracking is only available for IITM subjects.', 'error')
        return redirect(url_for('subjects.detail', subject_id=subject.id))

    weeks = subject.weekly_progress
    total_weeks = len(weeks)
    completed_weeks = sum(1 for w in weeks if w.status == 'Completed')
    in_progress_weeks = sum(1 for w in weeks if w.status == 'In Progress')
    next_week_number = (weeks[-1].week_number + 1) if weeks else 1

    return render_template(
        'progress/weekly-progress.html',
        subject=subject,
        weeks=weeks,
        total_weeks=total_weeks,
        completed_weeks=completed_weeks,
        in_progress_weeks=in_progress_weeks,
        next_week_number=next_week_number,
    )


@progress_bp.route('/subject/<int:subject_id>/add-week', methods=['POST'])
@login_required
def add_week(subject_id):
    """
    Add a new sequential week to the IITM subject's progress checklist.
    Automatically increments the highest existing week number.
    """
    subject = Subject.query.get_or_404(subject_id)

    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)

    if subject.university != 'IITM':
        flash('Weekly progress tracking is only available for IITM subjects.', 'error')
        return redirect(url_for('subjects.detail', subject_id=subject.id))

    # Auto-increment week number based on the maximum existing week for this subject
    max_week = (
        db.session.query(func.max(WeeklyProgress.week_number))
        .filter_by(subject_id=subject.id)
        .scalar()
    )
    next_week_num = (max_week or 0) + 1

    new_week = WeeklyProgress(
        subject_id=subject.id,
        week_number=next_week_num,
        status='Not Started'
    )

    try:
        db.session.add(new_week)
        db.session.commit()
        flash(f'Week {next_week_num} added successfully.', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred while adding the week. Please try again.', 'error')

    return redirect(url_for('progress.weekly_progress', subject_id=subject.id))


@progress_bp.route('/week/<int:week_id>/update-status', methods=['POST'])
@login_required
def update_status(week_id):
    """
    Update the completion status of a specific week entry.
    Validates that status is one of: 'Not Started', 'In Progress', 'Completed'.
    """
    week = WeeklyProgress.query.get_or_404(week_id)

    # Verify ownership via the associated subject
    if not week.subject or not week.subject.belongs_to_user(current_user.id):
        abort(403)

    new_status = request.form.get('status', '').strip()
    if new_status not in VALID_STATUSES:
        flash('Invalid status provided.', 'error')
        return redirect(url_for('progress.weekly_progress', subject_id=week.subject_id))

    week.status = new_status
    try:
        db.session.commit()
        flash(f'Week {week.week_number} marked as {new_status}.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update week status. Please try again.', 'error')

    return redirect(url_for('progress.weekly_progress', subject_id=week.subject_id))


@progress_bp.route('/week/<int:week_id>/delete', methods=['POST'])
@login_required
def delete_week(week_id):
    """
    Delete a specific week entry from the subject's progress checklist.
    """
    week = WeeklyProgress.query.get_or_404(week_id)

    # Verify ownership via the associated subject
    if not week.subject or not week.subject.belongs_to_user(current_user.id):
        abort(403)

    subject_id = week.subject_id
    week_number = week.week_number

    try:
        db.session.delete(week)
        db.session.commit()
        flash(f'Week {week_number} deleted successfully.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete week. Please try again.', 'error')

    return redirect(url_for('progress.weekly_progress', subject_id=subject_id))
