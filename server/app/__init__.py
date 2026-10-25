import os
import yaml
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

def create_app(test_config=None):
    # create and configure the app
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Secrets and instance-specific settings come from .env (never from tracked config).
    load_dotenv(os.path.join(project_root, '.env'))

    # Static folder for frontend build
    static_folder = os.path.join(project_root, 'web', 'dist')
    
    app = Flask(__name__, 
                static_folder=static_folder,
                static_url_path='/')
    
    # Load configuration
    # config.yaml is in the project root (PictureWeb/config.yaml)
    config_path = os.path.join(project_root, 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # Resolve relative paths relative to project root
            for key in ['DB_PATH', 'CACHE_DIR', 'TRASH_DIR']:
                if key in config and not os.path.isabs(config[key]):
                    config[key] = os.path.abspath(os.path.join(project_root, config[key]))
            
            app.config.update(config)

    # SECRET_KEY is mandatory: it signs login tokens and Flask sessions.
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            'SECRET_KEY is not configured. Copy .env.example to .env and set SECRET_KEY.'
        )
    app.config['SECRET_KEY'] = secret_key
    app.config['APP_ENV'] = os.environ.get('APP_ENV', 'dev')
    app.config['TOKEN_MAX_AGE_SECONDS'] = int(os.environ.get('TOKEN_MAX_AGE_SECONDS', '604800'))
    app.config['DEFAULT_ADMIN_USERNAME'] = os.environ.get('DEFAULT_ADMIN_USERNAME', '').strip()
    app.config['DEFAULT_ADMIN_PASSWORD'] = os.environ.get('DEFAULT_ADMIN_PASSWORD', '')

    if test_config:
        app.config.update(test_config)

    CORS(app) # Enable CORS for all routes

    # Initialize database
    from .utils import db
    db.init_app(app)
    
    # Register Blueprints
    from .routes import folder
    app.register_blueprint(folder.bp)

    from .routes import image
    app.register_blueprint(image.bp)

    from .routes import bookmarks
    app.register_blueprint(bookmarks.bp)

    from .routes import admin
    app.register_blueprint(admin.bp)

    from .routes import auth
    app.register_blueprint(auth.bp)

    from .routes import settings
    app.register_blueprint(settings.bp)
    
    # Auto-initialize DB if it doesn't exist
    with app.app_context():
        db.init_db()

        # Video support depends on external binaries; warn but never block image features.
        from .services.video import check_binaries, cleanup_video_temp
        binaries = check_binaries()
        for name in ('ffmpeg', 'ffprobe'):
            if not binaries[name]:
                app.logger.warning(
                    "Video support degraded: %s not found at %s "
                    "(configure FFMPEG_PATH/FFPROBE_PATH if it lives elsewhere)",
                    name, binaries[f'{name}_path']
                )
        cleanup_video_temp()

    # A simple page that says hello
    @app.route('/api/health')
    def health_check():
        return {'status': 'ok', 'message': 'PictureWeb Backend is running'}

    # Serve the frontend build (catch-all for SPA)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    return app
