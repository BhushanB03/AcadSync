from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models.subject import Subject

subjects_bp = Blueprint('subjects', __name__, url_prefix='/subjects')


@subjects_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    List all subjects belonging to the current user.
    Can be filtered by university and view (active/archived).
    
    Query Parameters:
        university (str, optional): 'VIT' or 'IITM' to filter subjects
        view (str, optional): 'active' (default) or 'archived'
            - 'active': shows subjects with status 'Active' or 'Completed'
            - 'archived': shows subjects with status 'Archived'
    """
    # Get optional filter parameters
    university_filter = request.args.get('university', None)
    view_mode = request.args.get('view', 'active').lower()
    
    # Validate view mode
    if view_mode not in ['active', 'archived']:
        view_mode = 'active'
    
    # Build query
    query = Subject.query.filter_by(user_id=current_user.id)
    
    # Filter by view mode
    if view_mode == 'active':
        # Show 'Active' and 'Completed' subjects
        query = query.filter(Subject.status.in_(['Active', 'Completed']))
    elif view_mode == 'archived':
        # Show 'Archived' subjects
        query = query.filter_by(status='Archived')
    
    # Filter by university if specified
    if university_filter and university_filter in ['VIT', 'IITM']:
        query = query.filter_by(university=university_filter)
    
    subjects = query.order_by(Subject.created_at.desc()).all()
    
    return render_template(
        'subjects/subjects.html',
        subjects=subjects,
        filter_university=university_filter,
        current_view=view_mode
    )


@subjects_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    Display form to add a new subject (GET) or create it (POST).
    The POST handler links the new subject to current_user.id.
    """
    if request.method == 'POST':
        # Collect form data
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        term = request.form.get('term', '').strip()
        subject_type = request.form.get('subject_type', '').strip()
        # University toggle: 'on' (from checkbox) means VIT, 'off' (no value) means IITM
        university = 'VIT' if request.form.get('university') == 'on' else 'IITM'
        
        # Validation
        if not all([name, code, term, subject_type]):
            flash('All fields are required.', 'error')
            return redirect(url_for('subjects.add'))
        
        if len(name) > 150:
            flash('Subject name must be 150 characters or less.', 'error')
            return redirect(url_for('subjects.add'))
        
        if len(code) > 50:
            flash('Subject code must be 50 characters or less.', 'error')
            return redirect(url_for('subjects.add'))
        
        # Create new subject linked to current user
        subject = Subject(
            user_id=current_user.id,
            name=name,
            code=code,
            term=term,
            subject_type=subject_type,
            university=university,
            status='Active'
        )
        
        try:
            db.session.add(subject)
            db.session.commit()
            flash(f'Subject "{name}" added successfully!', 'success')
            return redirect(url_for('subjects.detail', subject_id=subject.id))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while adding the subject. Please try again.', 'error')
            return redirect(url_for('subjects.add'))
    
    return render_template('subjects/add-subject.html')


@subjects_bp.route('/<int:subject_id>', methods=['GET'])
@login_required
def detail(subject_id):
    """
    Display detailed view of a subject.
    Includes placeholder sections for future features (Grade Calculator, Study Material, Tasks, Attendance).
    """
    subject = Subject.query.get_or_404(subject_id)
    
    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)
    
    return render_template('subjects/subject-detail.html', subject=subject)


@subjects_bp.route('/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(subject_id):
    """
    Edit an existing subject (GET shows form, POST updates it).
    Only the subject owner can edit.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)
    
    if request.method == 'POST':
        # Collect form data
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        term = request.form.get('term', '').strip()
        subject_type = request.form.get('subject_type', '').strip()
        university = 'VIT' if request.form.get('university') == 'on' else 'IITM'
        
        # Validation
        if not all([name, code, term, subject_type]):
            flash('All fields are required.', 'error')
            return redirect(url_for('subjects.edit', subject_id=subject_id))
        
        if len(name) > 150:
            flash('Subject name must be 150 characters or less.', 'error')
            return redirect(url_for('subjects.edit', subject_id=subject_id))
        
        if len(code) > 50:
            flash('Subject code must be 50 characters or less.', 'error')
            return redirect(url_for('subjects.edit', subject_id=subject_id))
        
        # Update subject
        subject.name = name
        subject.code = code
        subject.term = term
        subject.subject_type = subject_type
        subject.university = university
        
        try:
            db.session.commit()
            flash(f'Subject "{name}" updated successfully!', 'success')
            return redirect(url_for('subjects.detail', subject_id=subject_id))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating the subject. Please try again.', 'error')
            return redirect(url_for('subjects.edit', subject_id=subject_id))
    
    return render_template('subjects/edit-subject.html', subject=subject)


@subjects_bp.route('/<int:subject_id>/archive', methods=['POST'])
@login_required
def archive(subject_id):
    """
    Archive a subject by setting its status to 'Archived'.
    Only the subject owner can archive.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)
    
    subject.status = 'Archived'
    
    try:
        db.session.commit()
        flash(f'Subject "{subject.name}" archived successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while archiving the subject. Please try again.', 'error')
    
    return redirect(url_for('subjects.index'))


@subjects_bp.route('/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete(subject_id):
    """
    Delete a subject permanently.
    Only the subject owner can delete.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)
    
    subject_name = subject.name
    
    try:
        db.session.delete(subject)
        db.session.commit()
        flash(f'Subject "{subject_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"DELETE SUBJECT ERROR: {e}")  # TEMPORARY — remove after debugging
        import traceback
        traceback.print_exc()  # TEMPORARY — shows full traceback in terminal
        flash('An error occurred while deleting the subject. Please try again.', 'error')
    
    return redirect(url_for('subjects.index'))


@subjects_bp.route('/<int:subject_id>/unarchive', methods=['POST'])
@login_required
def unarchive(subject_id):
    """
    Unarchive a subject by setting its status back to 'Active'.
    Only the subject owner can unarchive.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    # Verify ownership
    if not subject.belongs_to_user(current_user.id):
        abort(403)
    
    subject.status = 'Active'
    
    try:
        db.session.commit()
        flash(f'Subject "{subject.name}" restored successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while restoring the subject. Please try again.', 'error')
    
    # Redirect back to archived view to show the subject has been unarchived
    return redirect(url_for('subjects.index', view='archived'))
