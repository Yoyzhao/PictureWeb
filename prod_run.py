import os
import sys
from waitress import serve
from server.app import create_app

# Ensure we're in the project root
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

# Check for frontend build
dist_path = os.path.join(project_root, 'web', 'dist')
if not os.path.exists(dist_path):
    print("Warning: Frontend build not found at web/dist. Please run 'npm run build' in the web directory.")

app = create_app()

if __name__ == '__main__':
    port = app.config.get('SERVER_PORT', 5000)
    print(f"Starting PictureWeb production server...")
    print(f"Server is listening on http://0.0.0.0:{port}")
    print(f"Press Ctrl+C to stop.")
    
    # Run using waitress
    try:
        serve(app, host='0.0.0.0', port=port, threads=8)
    except KeyboardInterrupt:
        print("\nStopping server...")
        sys.exit(0)
    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)
