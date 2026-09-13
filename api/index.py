import sys
import os

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Vercel Python runtime expects a WSGI/ASGI app
# The app is already a FastAPI (ASGI) application
handler = app
