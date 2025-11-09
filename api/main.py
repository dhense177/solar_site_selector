"""
Vercel serverless function wrapper for FastAPI
This file is required by Vercel to find the FastAPI application
"""
import sys
import os
import traceback

# Add backend directory to path so we can import api_server
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_path)

# Store import error if it occurs
import_error = None
import_traceback = None

try:
    from api_server import api_app
    # Vercel expects the app to be named 'app'
    app = api_app
except Exception as e:
    # Store the error for the error handler
    import_error = str(e)
    import_traceback = traceback.format_exc()
    
    # Create a minimal error app for debugging
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    error_app = FastAPI()
    
    @error_app.get("/")
    @error_app.get("/{path:path}")
    async def error_handler(path: str = ""):
        error_msg = f"Failed to import api_server: {import_error}\n\nTraceback:\n{import_traceback}"
        return JSONResponse(
            status_code=500,
            content={"error": error_msg, "traceback": import_traceback}
        )
    
    app = error_app

