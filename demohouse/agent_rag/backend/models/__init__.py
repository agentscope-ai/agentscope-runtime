# models/__init__.py
from flask_sqlalchemy import SQLAlchemy

# Initialize the database object
db = SQLAlchemy()

# Optional: You can add utility functions here if needed
def init_app(app):
    """Initialize the database with the Flask app."""
    db.init_app(app)