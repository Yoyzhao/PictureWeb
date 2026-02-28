import os
import yaml
from flask import Flask, send_from_directory
from flask_cors import CORS

def create_app(test_config=None):
    # create and configure the app
    # Static folder for frontend build
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    static_folder = os.path.join(project_root, 'web', 'dist')
    
    app = Flask(__name__, 
                instance_relative_config=True,
                static_folder=static_folder,
                static_url_path='/')
    
    # Load configuration
    # config.yaml is in the project root (PictureWeb/config.yaml)
    config_path = os.path.join(project_root, 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # Resolve relative paths relative to project root
            for key in ['DB_PATH', 'CACHE_DIR']:
                if key in config and not os.path.isabs(config[key]):
                    config[key] = os.path.abspath(os.path.join(project_root, config[key]))
            
            app.config.update(config)
    
    CORS(app) # Enable CORS for all routes

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize database
    from .utils import db
    db.init_app(app)
    
    # Register Blueprints
    from .routes import folder
    app.register_blueprint(folder.bp)

    from .routes import image
    app.register_blueprint(image.bp)

    from .routes import admin
    app.register_blueprint(admin.bp)

    from .routes import auth
    app.register_blueprint(auth.bp)
    
    # Auto-initialize DB if it doesn't exist
    with app.app_context():
        db.init_db()

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
