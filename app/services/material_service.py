import os
import uuid
from typing import Tuple

from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename: str) -> bool:
    """Return True when the file extension is in the configured upload whitelist."""
    if not filename:
        return False

    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return extension in current_app.config.get('ALLOWED_UPLOAD_EXTENSIONS', set())


def save_uploaded_file(file, subject_id: int) -> Tuple[str, str, int]:
    """
    Save an uploaded file into a per-subject directory under the app upload folder.

    Returns a tuple of:
        (relative_file_path, original_filename, file_size)

    The relative path is stored in the DB so the file can be served with
    send_from_directory(current_app.config['UPLOAD_FOLDER'], relative_path).
    """
    if file is None or file.filename == '':
        raise ValueError('No file selected')

    if not allowed_file(file.filename):
        raise ValueError('File type not allowed')

    upload_folder = current_app.config['UPLOAD_FOLDER']
    subject_folder = os.path.join(upload_folder, f'subject_{subject_id}')
    os.makedirs(subject_folder, exist_ok=True)

    original_filename = secure_filename(file.filename)
    extension = os.path.splitext(original_filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{extension}"
    final_path = os.path.join(subject_folder, unique_name)

    file.save(final_path)
    file_size = os.path.getsize(final_path)
    relative_path = os.path.relpath(final_path, upload_folder).replace('\\', '/')
    return relative_path, original_filename, file_size


def delete_material_file(file_path: str) -> None:
    """Delete a file from disk if it still exists, without crashing if it is already missing."""
    if not file_path:
        return

    safe_path = file_path.replace('/', os.sep).replace('\\', os.sep)
    if not os.path.isabs(safe_path):
        safe_path = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_path)

    try:
        if os.path.exists(safe_path):
            os.remove(safe_path)
    except OSError:
        # Ignore missing or inaccessible files during cleanup.
        pass
