"""
Grades blueprint: routes for grade templates, formula management, and grade calculation.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.subject import Subject
from app.models.grade_template import GradeTemplate
from app.models.assessment import (
    GradeTemplateComponent,
    GradeTemplateGradeBoundary,
    SubjectComponent,
    SubjectGradeBoundary
)
from app.services.formula_engine import validate_formula, evaluate_formula
from app.services.grade_service import (
    get_percentage_values,
    calculate_final_score,
    get_grade_for_score,
    calculate_target_grade,
    apply_template_to_subject
)

grades_bp = Blueprint('grades', __name__, url_prefix='/grades')


def _parse_grade_boundaries_from_form(form_data):
    """Collect and normalize grade boundaries from a submitted form.

    Users provide only each grade's minimum threshold. The max score for every grade is
    derived automatically in descending order so ranges do not overlap or leave gaps.
    """
    raw_boundaries = []
    i = 0
    while f'grade_label_{i}' in form_data:
        grade_label = form_data.get(f'grade_label_{i}', '').strip()
        min_score_str = form_data.get(f'min_score_{i}', '').strip()

        if grade_label and min_score_str:
            try:
                min_score = float(min_score_str)
            except ValueError as exc:
                raise ValueError(f'Invalid minimum score for grade {grade_label}') from exc

            raw_boundaries.append({
                'label': grade_label,
                'min': min_score
            })
        i += 1

    if not raw_boundaries:
        return []

    sorted_boundaries = sorted(raw_boundaries, key=lambda item: item['min'], reverse=True)
    calculated = []

    for index, boundary in enumerate(sorted_boundaries):
        # Keep the top grade at 100. For a grading scale that can exceed 100, adjust this
        # constant to that subject's max score instead.
        if index == 0:
            max_score = 100.0
        else:
            upper_threshold = sorted_boundaries[index - 1]['min']
            max_score = upper_threshold - 0.01

        calculated.append({
            'label': boundary['label'],
            'min': boundary['min'],
            'max': round(max_score, 2)
        })

    return calculated


# ============================================================================
# TEMPLATE MANAGEMENT ROUTES
# ============================================================================

@grades_bp.route('/templates', methods=['GET'])
@login_required
def list_templates():
    """
    List all grade templates for the current user.
    """
    templates = GradeTemplate.query.filter_by(user_id=current_user.id).all()
    return render_template('grades/grade-templates.html', templates=templates)


@grades_bp.route('/templates/add', methods=['GET', 'POST'])
@login_required
def add_template():
    """
    Create a new grade template.
    
    GET: Show template creation form
    POST: Validate and save new template with components, boundaries, and formula
    """
    if request.method == 'GET':
        return render_template('grades/template-form.html', template=None)
    
    # POST: Validate and save template
    name = request.form.get('name', '').strip()
    university = request.form.get('university', 'VIT')
    formula_text = request.form.get('formula_text', '').strip()
    calculation_mode = (request.form.get('calculation_mode', 'raw') or 'raw').strip().lower()
    if calculation_mode not in {'raw', 'percentage'}:
        calculation_mode = 'raw'

    # Validate required fields
    if not name:
        flash('Template name is required', 'error')
        return redirect(url_for('grades.add_template'))
    
    if not formula_text:
        flash('Formula is required', 'error')
        return redirect(url_for('grades.add_template'))
    
    # Parse components from form (dynamic rows: component_code_N, component_name_N, max_marks_N)
    components_data = []
    i = 0
    while f'component_code_{i}' in request.form:
        code = request.form.get(f'component_code_{i}', '').strip()
        name_field = request.form.get(f'component_name_{i}', '').strip()
        max_marks_str = request.form.get(f'max_marks_{i}', '').strip()
        
        if code and name_field and max_marks_str:
            try:
                max_marks = float(max_marks_str)
                components_data.append({
                    'code': code,
                    'name': name_field,
                    'max_marks': max_marks
                })
            except ValueError:
                flash(f'Invalid max_marks for component {code}', 'error')
                return redirect(url_for('grades.add_template'))
        i += 1
    
    if not components_data:
        flash('At least one component is required', 'error')
        return redirect(url_for('grades.add_template'))
    
    # Validate formula against component codes
    component_codes = [c['code'] for c in components_data]
    is_valid, error_msg = validate_formula(formula_text, component_codes)
    if not is_valid:
        flash(f'Formula error: {error_msg}', 'error')
        return redirect(url_for('grades.add_template'))
    
    # Parse grade boundaries: each row only contains the minimum threshold; max score is
    # derived automatically after sorting by min_score in descending order.
    try:
        boundaries_data = _parse_grade_boundaries_from_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('grades.add_template'))

    if not boundaries_data:
        flash('At least one grade boundary is required', 'error')
        return redirect(url_for('grades.add_template'))
    
    # Create and save template
    try:
        template = GradeTemplate(
            user_id=current_user.id,
            name=name,
            university=university,
            formula_text=formula_text,
            calculation_mode=calculation_mode
        )
        db.session.add(template)
        db.session.flush()  # Get template.id
        
        # Add components
        for comp in components_data:
            component = GradeTemplateComponent(
                template_id=template.id,
                component_code=comp['code'],
                component_name=comp['name'],
                max_marks=comp['max_marks']
            )
            db.session.add(component)
        
        # Add grade boundaries
        for boundary in boundaries_data:
            grade_boundary = GradeTemplateGradeBoundary(
                template_id=template.id,
                grade_label=boundary['label'],
                min_score=boundary['min'],
                max_score=boundary['max']
            )
            db.session.add(grade_boundary)
        
        db.session.commit()
        flash(f'Template "{name}" created successfully', 'success')
        return redirect(url_for('grades.list_templates'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating template: {str(e)}', 'error')
        return redirect(url_for('grades.add_template'))


@grades_bp.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """
    Edit an existing grade template.
    Verify ownership before allowing edit.
    """
    template = GradeTemplate.query.get_or_404(template_id)
    
    # Ownership check
    if not template.belongs_to_user(current_user.id):
        flash('You do not have permission to edit this template', 'error')
        return redirect(url_for('grades.list_templates')), 403
    
    if request.method == 'GET':
        return render_template('grades/template-form.html', template=template)
    
    # POST: Update template
    name = request.form.get('name', '').strip()
    university = request.form.get('university', 'VIT')
    formula_text = request.form.get('formula_text', '').strip()
    calculation_mode = (request.form.get('calculation_mode', 'raw') or 'raw').strip().lower()
    if calculation_mode not in {'raw', 'percentage'}:
        calculation_mode = 'raw'

    if not name or not formula_text:
        flash('Name and formula are required', 'error')
        return redirect(url_for('grades.edit_template', template_id=template_id))
    
    # Parse components and boundaries (same as add_template)
    components_data = []
    i = 0
    while f'component_code_{i}' in request.form:
        code = request.form.get(f'component_code_{i}', '').strip()
        name_field = request.form.get(f'component_name_{i}', '').strip()
        max_marks_str = request.form.get(f'max_marks_{i}', '').strip()
        
        if code and name_field and max_marks_str:
            try:
                max_marks = float(max_marks_str)
                components_data.append({
                    'code': code,
                    'name': name_field,
                    'max_marks': max_marks
                })
            except ValueError:
                flash(f'Invalid max_marks for component {code}', 'error')
                return redirect(url_for('grades.edit_template', template_id=template_id))
        i += 1
    
    if not components_data:
        flash('At least one component is required', 'error')
        return redirect(url_for('grades.edit_template', template_id=template_id))
    
    # Validate formula
    component_codes = [c['code'] for c in components_data]
    is_valid, error_msg = validate_formula(formula_text, component_codes)
    if not is_valid:
        flash(f'Formula error: {error_msg}', 'error')
        return redirect(url_for('grades.edit_template', template_id=template_id))
    
    # Parse grade boundaries: users enter only the minimum threshold; the max score is
    # derived automatically from the sorted order.
    try:
        boundaries_data = _parse_grade_boundaries_from_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('grades.edit_template', template_id=template_id))

    if not boundaries_data:
        flash('At least one grade boundary is required', 'error')
        return redirect(url_for('grades.edit_template', template_id=template_id))
    
    # Update template
    try:
        template.name = name
        template.university = university
        template.formula_text = formula_text
        template.calculation_mode = calculation_mode

        # Clear and re-add components
        template.components.clear()
        for comp in components_data:
            component = GradeTemplateComponent(
                template_id=template.id,
                component_code=comp['code'],
                component_name=comp['name'],
                max_marks=comp['max_marks']
            )
            db.session.add(component)
        
        # Clear and re-add boundaries
        template.grade_boundaries.clear()
        for boundary in boundaries_data:
            grade_boundary = GradeTemplateGradeBoundary(
                template_id=template.id,
                grade_label=boundary['label'],
                min_score=boundary['min'],
                max_score=boundary['max']
            )
            db.session.add(grade_boundary)
        
        db.session.commit()
        flash('Template updated successfully', 'success')
        return redirect(url_for('grades.list_templates'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating template: {str(e)}', 'error')
        return redirect(url_for('grades.edit_template', template_id=template_id))


@grades_bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    """
    Delete a grade template (ownership verified).
    """
    template = GradeTemplate.query.get_or_404(template_id)
    
    if not template.belongs_to_user(current_user.id):
        flash('You do not have permission to delete this template', 'error')
        return redirect(url_for('grades.list_templates')), 403
    
    try:
        template_name = template.name
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{template_name}" deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting template: {str(e)}', 'error')
    
    return redirect(url_for('grades.list_templates'))


# ============================================================================
# SUBJECT GRADE CALCULATOR ROUTES
# ============================================================================

@grades_bp.route('/subject/<int:subject_id>', methods=['GET'])
@login_required
def grade_calculator(subject_id):
    """
    Main grade calculator page for a subject.
    Shows components, formula, calculated score, and grade.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    if not subject.belongs_to_user(current_user.id):
        return redirect(url_for('subjects.index')), 403
    
    # Get available templates for "Apply Template" form
    templates = GradeTemplate.query.filter_by(user_id=current_user.id).all()
    
    # Calculate current final score and grade
    final_score, score_message = calculate_final_score(subject)
    grade = None
    if final_score is not None:
        grade = get_grade_for_score(final_score, subject.grade_boundaries)
    
    return render_template(
        'grades/grade-calculator.html',
        subject=subject,
        final_score=final_score,
        score_message=score_message,
        grade=grade,
        templates=templates
    )


@grades_bp.route('/subject/<int:subject_id>/apply-template', methods=['POST'])
@login_required
def apply_template(subject_id):
    """
    Apply a saved template to a subject.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    if not subject.belongs_to_user(current_user.id):
        flash('Unauthorized', 'error')
        return redirect(url_for('subjects.index')), 403
    
    template_id = request.form.get('template_id')
    if not template_id:
        flash('No template selected', 'error')
        return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
    
    template = GradeTemplate.query.get_or_404(template_id)
    if not template.belongs_to_user(current_user.id):
        flash('Template not found', 'error')
        return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
    
    try:
        message = apply_template_to_subject(template, subject)
        flash(message, 'success')
    except ValueError as e:
        flash(f'Error applying template: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('grades.grade_calculator', subject_id=subject_id))


@grades_bp.route('/subject/<int:subject_id>/custom-setup', methods=['GET', 'POST'])
@login_required
def custom_setup(subject_id):
    """
    Create a custom (non-template) formula setup directly on a subject.
    Same fields as template creation but saves to subject instead.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    if not subject.belongs_to_user(current_user.id):
        return redirect(url_for('subjects.index')), 403
    
    if request.method == 'GET':
        return render_template('grades/custom-setup.html', subject=subject)
    
    # POST: Create custom setup
    formula_text = request.form.get('formula_text', '').strip()
    calculation_mode = (request.form.get('calculation_mode', 'raw') or 'raw').strip().lower()
    if calculation_mode not in {'raw', 'percentage'}:
        calculation_mode = 'raw'

    if not formula_text:
        flash('Formula is required', 'error')
        return redirect(url_for('grades.custom_setup', subject_id=subject_id))
    
    # Parse components
    components_data = []
    i = 0
    while f'component_code_{i}' in request.form:
        code = request.form.get(f'component_code_{i}', '').strip()
        name_field = request.form.get(f'component_name_{i}', '').strip()
        max_marks_str = request.form.get(f'max_marks_{i}', '').strip()
        
        if code and name_field and max_marks_str:
            try:
                max_marks = float(max_marks_str)
                components_data.append({
                    'code': code,
                    'name': name_field,
                    'max_marks': max_marks
                })
            except ValueError:
                flash(f'Invalid max_marks for component {code}', 'error')
                return redirect(url_for('grades.custom_setup', subject_id=subject_id))
        i += 1
    
    if not components_data:
        flash('At least one component is required', 'error')
        return redirect(url_for('grades.custom_setup', subject_id=subject_id))
    
    # Validate formula
    component_codes = [c['code'] for c in components_data]
    is_valid, error_msg = validate_formula(formula_text, component_codes)
    if not is_valid:
        flash(f'Formula error: {error_msg}', 'error')
        return redirect(url_for('grades.custom_setup', subject_id=subject_id))
    
    # Parse grade boundaries: users enter only the minimum threshold; the max score is
    # derived automatically from the sorted order.
    try:
        boundaries_data = _parse_grade_boundaries_from_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('grades.custom_setup', subject_id=subject_id))

    if not boundaries_data:
        flash('At least one grade boundary is required', 'error')
        return redirect(url_for('grades.custom_setup', subject_id=subject_id))
    
    # Clear existing components and boundaries
    subject.components.clear()
    subject.grade_boundaries.clear()
    
    # Add components
    try:
        for comp in components_data:
            component = SubjectComponent(
                subject_id=subject.id,
                component_code=comp['code'],
                component_name=comp['name'],
                max_marks=comp['max_marks'],
                obtained_marks=None
            )
            db.session.add(component)
        
        # Add grade boundaries
        for boundary in boundaries_data:
            grade_boundary = SubjectGradeBoundary(
                subject_id=subject.id,
                grade_label=boundary['label'],
                min_score=boundary['min'],
                max_score=boundary['max']
            )
            db.session.add(grade_boundary)
        
        # Set formula and calculation mode on subject
        subject.formula_text = formula_text
        subject.calculation_mode = calculation_mode

        db.session.commit()
        flash('Custom formula setup created successfully', 'success')
        return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating setup: {str(e)}', 'error')
        return redirect(url_for('grades.custom_setup', subject_id=subject_id))


@grades_bp.route('/subject/<int:subject_id>/update-marks', methods=['POST'])
@login_required
def update_marks(subject_id):
    """
    Update obtained marks for subject components.
    Expects form data: obtained_marks_<component_id> for each component.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    if not subject.belongs_to_user(current_user.id):
        flash('Unauthorized', 'error')
        return redirect(url_for('subjects.index')), 403
    
    try:
        # Update each component's obtained_marks
        for component in subject.components:
            marks_key = f'obtained_marks_{component.id}'
            marks_str = request.form.get(marks_key, '').strip()
            
            if marks_str:
                try:
                    obtained = float(marks_str)
                    # Validate that obtained <= max_marks
                    if obtained > component.max_marks:
                        flash(f'{component.component_name}: obtained marks cannot exceed {component.max_marks}', 'error')
                        return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
                    if obtained < 0:
                        flash(f'{component.component_name}: marks cannot be negative', 'error')
                        return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
                    component.obtained_marks = obtained
                except ValueError:
                    flash(f'{component.component_name}: invalid marks format', 'error')
                    return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
            else:
                # Empty field = clear the marks
                component.obtained_marks = None
        
        db.session.commit()
        flash('Marks updated successfully', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating marks: {str(e)}', 'error')
    
    return redirect(url_for('grades.grade_calculator', subject_id=subject_id))


@grades_bp.route('/subject/<int:subject_id>/target', methods=['GET', 'POST'])
@login_required
def target_grade(subject_id):
    """
    Target grade calculator: calculate required marks for a target grade.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    if not subject.belongs_to_user(current_user.id):
        return redirect(url_for('subjects.index')), 403
    
    if not subject.formula_text:
        flash('No formula configured for this subject', 'error')
        return redirect(url_for('grades.grade_calculator', subject_id=subject_id))
    
    target_grade_label = None
    achievable = None
    required_pct = None
    message = None
    
    if request.method == 'POST':
        target_grade_label = request.form.get('target_grade', '').strip()
        
        if not target_grade_label:
            flash('Please select a target grade', 'error')
        else:
            achievable, required_pct, message = calculate_target_grade(subject, target_grade_label)
            flash(message, 'info')
    
    return render_template(
        'grades/target-grade.html',
        subject=subject,
        achievable=achievable,
        required_pct=required_pct,
        message=message,
        target_grade_label=target_grade_label
    )
