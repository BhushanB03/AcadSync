from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import RequestEntityTooLarge

from app.extensions import db
from app.models.study_material import StudyMaterial
from app.models.subject import Subject
from app.services.material_service import delete_material_file, save_uploaded_file

materials_bp = Blueprint('materials', __name__, url_prefix='/materials')

CATEGORY_LABELS = {
    'lecture_notes': 'Lecture Notes',
    'exam_papers': 'Exam Papers'
}


def _verify_subject_access(subject_id: int):
    subject = Subject.query.get_or_404(subject_id)
    if not subject.belongs_to_user(current_user.id):
        return None, redirect(url_for('subjects.index')), 403
    return subject, None, None


@materials_bp.route('/subject/<int:subject_id>', methods=['GET'])
@login_required
def study_material_home(subject_id):
    subject, redirect_response, status_code = _verify_subject_access(subject_id)
    if redirect_response is not None:
        return redirect_response, status_code

    lecture_count = StudyMaterial.query.filter_by(subject_id=subject.id, category='lecture_notes').count()
    exam_count = StudyMaterial.query.filter_by(subject_id=subject.id, category='exam_papers').count()

    return render_template(
        'materials/study-material-home.html',
        subject=subject,
        lecture_count=lecture_count,
        exam_count=exam_count
    )


@materials_bp.route('/subject/<int:subject_id>/<category>', methods=['GET'])
@login_required
def category_list(subject_id, category):
    if category not in CATEGORY_LABELS:
        flash('Invalid study material category', 'error')
        return redirect(url_for('materials.study_material_home', subject_id=subject_id))

    subject, redirect_response, status_code = _verify_subject_access(subject_id)
    if redirect_response is not None:
        return redirect_response, status_code

    materials = StudyMaterial.query.filter_by(subject_id=subject.id, category=category).order_by(StudyMaterial.created_at.desc()).all()
    return render_template(
        'materials/category-list.html',
        subject=subject,
        category=category,
        category_label=CATEGORY_LABELS[category],
        materials=materials
    )


@materials_bp.route('/subject/<int:subject_id>/<category>/upload', methods=['GET', 'POST'])
@login_required
def upload_file(subject_id, category):
    if category not in CATEGORY_LABELS:
        flash('Invalid study material category', 'error')
        return redirect(url_for('materials.study_material_home', subject_id=subject_id))

    subject, redirect_response, status_code = _verify_subject_access(subject_id)
    if redirect_response is not None:
        return redirect_response, status_code

    if request.method == 'GET':
        return render_template('materials/upload-file.html', subject=subject, category=category, category_label=CATEGORY_LABELS[category])

    try:
        uploaded_file = request.files.get('file')
        title = request.form.get('title', '').strip()

        if not title:
            flash('Material title is required', 'error')
            return redirect(url_for('materials.upload_file', subject_id=subject_id, category=category))

        if uploaded_file is None or uploaded_file.filename == '':
            flash('Please select a file to upload', 'error')
            return redirect(url_for('materials.upload_file', subject_id=subject_id, category=category))

        from app.config import Config
        if uploaded_file.filename.rsplit('.', 1)[-1].lower() not in Config.ALLOWED_UPLOAD_EXTENSIONS:
            flash('File type is not allowed. Allowed: PDF, PPT, PPTX, DOC, DOCX, PNG, JPG, JPEG', 'error')
            return redirect(url_for('materials.upload_file', subject_id=subject_id, category=category))

        file_path, original_filename, file_size = save_uploaded_file(uploaded_file, subject.id)

        material = StudyMaterial(
            subject_id=subject.id,
            category=category,
            material_type='file',
            title=title,
            file_path=file_path,
            original_filename=original_filename,
            file_size=file_size
        )
        db.session.add(material)
        db.session.commit()

        flash('File uploaded successfully', 'success')
        return redirect(url_for('materials.category_list', subject_id=subject_id, category=category))
    except RequestEntityTooLarge:
        flash('Uploaded file exceeds the 16 MB limit.', 'error')
        return redirect(url_for('materials.upload_file', subject_id=subject_id, category=category))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('materials.upload_file', subject_id=subject_id, category=category))


@materials_bp.route('/subject/<int:subject_id>/<category>/add-link', methods=['GET', 'POST'])
@login_required
def add_link(subject_id, category):
    if category not in CATEGORY_LABELS:
        flash('Invalid study material category', 'error')
        return redirect(url_for('materials.study_material_home', subject_id=subject_id))

    subject, redirect_response, status_code = _verify_subject_access(subject_id)
    if redirect_response is not None:
        return redirect_response, status_code

    if request.method == 'GET':
        return render_template('materials/add-link.html', subject=subject, category=category, category_label=CATEGORY_LABELS[category])

    title = request.form.get('title', '').strip()
    url = request.form.get('url', '').strip()

    if not title:
        flash('Link title is required', 'error')
        return redirect(url_for('materials.add_link', subject_id=subject_id, category=category))

    if not url:
        flash('Please provide a URL', 'error')
        return redirect(url_for('materials.add_link', subject_id=subject_id, category=category))

    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        flash('Please enter a valid URL starting with http:// or https://', 'error')
        return redirect(url_for('materials.add_link', subject_id=subject_id, category=category))

    material = StudyMaterial(
        subject_id=subject.id,
        category=category,
        material_type='link',
        title=title,
        url=url
    )
    db.session.add(material)
    db.session.commit()

    flash('Link added successfully', 'success')
    return redirect(url_for('materials.category_list', subject_id=subject_id, category=category))


@materials_bp.route('/subject/<int:subject_id>/<category>/add-note', methods=['GET', 'POST'])
@login_required
def add_note(subject_id, category):
    if category not in CATEGORY_LABELS:
        flash('Invalid study material category', 'error')
        return redirect(url_for('materials.study_material_home', subject_id=subject_id))

    subject, redirect_response, status_code = _verify_subject_access(subject_id)
    if redirect_response is not None:
        return redirect_response, status_code

    if request.method == 'GET':
        return render_template('materials/add-note.html', subject=subject, category=category, category_label=CATEGORY_LABELS[category])

    title = request.form.get('title', '').strip()
    note_content = request.form.get('note_content', '').strip()

    if not title:
        flash('Note title is required', 'error')
        return redirect(url_for('materials.add_note', subject_id=subject_id, category=category))

    material = StudyMaterial(
        subject_id=subject.id,
        category=category,
        material_type='note',
        title=title,
        note_content=note_content
    )
    db.session.add(material)
    db.session.commit()

    flash('Note added successfully', 'success')
    return redirect(url_for('materials.category_list', subject_id=subject_id, category=category))


@materials_bp.route('/material/<int:material_id>/delete', methods=['POST'])
@login_required
def delete_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    subject = material.subject

    if not subject or subject.user_id != current_user.id:
        flash('You do not have permission to delete this material', 'error')
        return redirect(url_for('subjects.index'))

    category = material.category
    if material.material_type == 'file' and material.file_path:
        delete_material_file(material.file_path)

    db.session.delete(material)
    db.session.commit()

    flash('Material deleted successfully', 'success')
    return redirect(url_for('materials.category_list', subject_id=subject.id, category=category))


@materials_bp.route('/material/<int:material_id>/download', methods=['GET'])
@login_required
def download_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    if material.subject is None or material.subject.user_id != current_user.id:
        flash('You do not have permission to access this file', 'error')
        return redirect(url_for('subjects.index'))

    if material.material_type != 'file' or not material.file_path:
        flash('This material is not a downloadable file', 'error')
        return redirect(url_for('materials.category_list', subject_id=material.subject.id, category=material.category))

    relative_path = material.file_path.replace('\\', '/')
    file_name = relative_path.rsplit('/', 1)[-1]
    return send_from_directory(
        directory=current_app.config['UPLOAD_FOLDER'],
        path=relative_path,
        as_attachment=True,
        download_name=material.original_filename or file_name
    )
