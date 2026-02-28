import sys
import os

# Add the server directory to sys.path so we can import app
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app import create_app
from app.utils.db import init_db

def main():
    app = create_app()
    with app.app_context():
        init_db()
    print("Database initialized successfully.")

if __name__ == "__main__":
    main()
