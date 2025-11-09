"""
Vercel serverless function wrapper for FastAPI
This file is required by Vercel to find the FastAPI application
"""
import sys
import os
import traceback

# Add parent directory to path so we can import api_server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from api_server import api_app
    # Vercel expects the app to be named 'app'
    app = api_app
except Exception as e:
    # Create a minimal error app for debugging
    from fastapi import FastAPI
    error_app = FastAPI()
    
    @error_app.get("/")
    @error_app.get("/{path:path}")
    async def error_handler(path: str = ""):
        error_msg = f"Failed to import api_server: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return {"error": error_msg, "traceback": traceback.format_exc()}
    
    app = error_app

