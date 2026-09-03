
import os
from dotenv import load_dotenv

load_dotenv()

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS = {'pdf', 'ppt', 'pptx', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
    UPLOAD_FOLDER = os.path.join(project_root, 'uploads')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')