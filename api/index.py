"""
Vercel serverless function wrapper for FastAPI
This file is required by Vercel to find the FastAPI application
"""
import sys
import os

# Add backend directory to path so we can import api_server
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_path)

from api_server import api_app

# Vercel expects the app to be named 'app'
app = api_app

