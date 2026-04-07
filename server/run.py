import os
import sys

# Ensure we can import from app
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = app.config.get('SERVER_PORT', 5000)
    app.run(host='0.0.0.0', port=port, debug=True)

