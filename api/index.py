"""
Vercel serverless function wrapper for FastAPI
This file is required by Vercel to find the FastAPI application
"""
import sys
import os

# Add parent directory to path so we can import api_server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_server import api_app

# Vercel expects the app to be named 'app'
app = api_app

