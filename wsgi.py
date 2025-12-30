"""WSGI entrypoint for production servers (e.g., gunicorn).
Import ``application`` from here: gunicorn wsgi:application
"""

from app import app as application

__all__ = ["application"]
