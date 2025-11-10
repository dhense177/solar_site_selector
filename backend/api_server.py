"""
FastAPI server for integrating sql_agent.py with the frontend
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from sql_agent import app as sql_agent_app
from langchain_core.runnables import RunnableConfig
from shapely.geometry import mapping as shapely_mapping
from geoalchemy2.shape import to_shape
import json
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Initialize FastAPI app
api_app = FastAPI(title="Solar Parcel Search API")

# Add middleware to log all requests for debugging
@api_app.middleware("http")
async def log_requests(request, call_next):
    print(f"Request: {request.method} {request.url.path}")
    print(f"Request headers: {dict(request.headers)}")
    response = await call_next(request)
    print(f"Response: {response.status_code}")
    return response

# Add error handler for debugging
# HTTPException should be handled by FastAPI's default handler
# Only catch non-HTTP exceptions
@api_app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi import HTTPException
    # If it's an HTTPException, let FastAPI handle it (don't catch it)
    if isinstance(exc, HTTPException):
        raise exc
    # Only handle non-HTTP exceptions
    import traceback
    error_details = {
        "error": str(exc),
        "type": type(exc).__name__,
        "traceback": traceback.format_exc()
    }
    print(f"ERROR: {error_details}")  # Log to Vercel logs
    return {"error": "Internal Server Error", "details": str(exc), "traceback": traceback.format_exc()}

# Configure CORS
# Get allowed origins from environment variable or use defaults
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # Strip whitespace and trailing slashes from origins
    allowed_origins = [origin.strip().rstrip('/') for origin in allowed_origins_env.split(",")]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:4173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8080",
    ]

# Log allowed origins for debugging
print(f"CORS allowed origins: {allowed_origins}")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Request/Response models
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ParcelResponse(BaseModel):
    address: str
    county: str
    acreage: float
    municipality: str
    owner_name: str
    total_value: float
    capacity: float  # ground_mounted_capacity_kw
    explanation: str
    geometry: Dict[str, Any]  # GeoJSON geometry - REQUIRED

class SearchResponse(BaseModel):
    parcels: List[ParcelResponse]
    summary: str
    sql: Optional[str] = None
    session_id: Optional[str] = None


def convert_geometry_to_geojson(geom_data: Any) -> Optional[Dict[str, Any]]:
    """Convert PostGIS geometry to GeoJSON dict"""
    if geom_data is None:
        return None
    
    # Already GeoJSON dict
    if isinstance(geom_data, dict):
        if 'type' in geom_data and 'coordinates' in geom_data:
            # Ensure coordinates are lists, not tuples
            return json.loads(json.dumps(geom_data))
        return None
    
    # String - could be JSON or hex-encoded WKB
    if isinstance(geom_data, str):
        geom_data = geom_data.strip()
        if not geom_data:
            return None
        
        # Try parsing as JSON first
        try:
            parsed = json.loads(geom_data)
            if isinstance(parsed, dict) and 'type' in parsed and 'coordinates' in parsed:
                return json.loads(json.dumps(parsed))  # Convert tuples to lists
        except:
            pass
        
        # Try as hex-encoded WKB (PostGIS returns geometry as hex WKB string)
        if len(geom_data) > 20:
            try:
                from shapely import wkb
                shapely_geom = wkb.loads(geom_data, hex=True)
                geo_json = shapely_mapping(shapely_geom)
                if isinstance(geo_json, dict) and 'type' in geo_json and 'coordinates' in geo_json:
                    # Convert tuples to lists (GeoJSON requires lists, not tuples)
                    return json.loads(json.dumps(geo_json))
            except:
                try:
                    from shapely import wkb
                    shapely_geom = wkb.loads(geom_data)
                    geo_json = shapely_mapping(shapely_geom)
                    if isinstance(geo_json, dict) and 'type' in geo_json and 'coordinates' in geo_json:
                        return json.loads(json.dumps(geo_json))
                except:
                    pass
    
    # PostGIS geometry object - convert to GeoJSON
    try:
        shapely_geom = to_shape(geom_data)
        geo_json = shapely_mapping(shapely_geom)
        if isinstance(geo_json, dict) and 'type' in geo_json and 'coordinates' in geo_json:
            return json.loads(json.dumps(geo_json))
    except:
        try:
            if hasattr(geom_data, '__geo_interface__'):
                geo_json = geom_data.__geo_interface__
                if isinstance(geo_json, dict) and 'type' in geo_json and 'coordinates' in geo_json:
                    return json.loads(json.dumps(geo_json))
        except:
            pass
        
        try:
            if isinstance(geom_data, bytes):
                from shapely import wkb
                shapely_geom = wkb.loads(geom_data)
                geo_json = shapely_mapping(shapely_geom)
                if isinstance(geo_json, dict) and 'type' in geo_json and 'coordinates' in geo_json:
                    return json.loads(json.dumps(geo_json))
        except:
            pass
    
    return None


def transform_row_to_parcel(row: Dict[str, Any], explanation: Optional[str] = None) -> Optional[ParcelResponse]:
    """Transform SQL result row to ParcelResponse"""
    try:
        address = row.get('full_address') or row.get('address') or ''
        county = row.get('county_name') or row.get('county') or ''
        acreage = float(row.get('area_acres') or row.get('acreage') or 0)
        municipality = row.get('municipality_name') or row.get('municipality') or ''
        owner_name = row.get('owner_name') or ''
        total_value = row.get('total_value')
        try:
            total_value = float(total_value) if total_value is not None else 0.0
        except:
            total_value = 0.0
        capacity = row.get('ground_mounted_capacity_kw') or row.get('capacity')
        try:
            capacity = float(capacity) if capacity is not None else 0.0
        except:
            capacity = 0.0
        
        # Convert geometry to GeoJSON - this is REQUIRED
        geom_data = row.get('geometry')
        if geom_data is None:
            return None
            
        geo_json = convert_geometry_to_geojson(geom_data)
        if not geo_json:
            return None
        
        return ParcelResponse(
            address=address,
            county=county,
            acreage=acreage,
            municipality=municipality,
            owner_name=owner_name,
            total_value=total_value,
            capacity=capacity,
            explanation=explanation or "Found parcel matching your criteria",
            geometry=geo_json
        )
    except Exception:
        return None


@api_app.options("/api/search")
async def search_parcels_options():
    """Handle CORS preflight for /api/search"""
    from fastapi.responses import Response
    print("Handling OPTIONS request for /api/search")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

# Map node names to user-friendly step names
STEP_NAMES = {
    "topic_filter": "Checking topic relevance",
    "contextual_query_understanding": "Constructing contextual query",
    "resolve_vague_conditions": "Resolving vague conditions",
    "generate_sql": "Generating SQL query",
    "execute_sql": "Executing query",
    "validate_sql": "Validating results",
    "repair_sql": "Repairing SQL query",
    "display_results": "Finalizing results"
}

async def stream_search_parcels(request: QueryRequest):
    """Stream search for parcels with real-time status updates"""
    session_id = request.session_id or str(uuid.uuid4())
    config = RunnableConfig(configurable={"thread_id": session_id})
    
    # Build state matching SQLState TypedDict
    state = {
        "user_query": request.query,
        "expanded_query": None,
        "sql_query": None,
        "results": None,
        "error": None,
        "last_failed_sql": None,
        "attempt": 0,
        "conversation": []
    }
    
    async def generate():
        try:
            # Stream the graph execution
            final_state = None
            # Use astream_events for better streaming support
            try:
                async for event in sql_agent_app.astream_events(state, config, version="v2"):
                    # Check if this is a node start event
                    if event.get("event") == "on_chain_start" and "name" in event:
                        node_name = event.get("name", "")
                        if node_name in STEP_NAMES:
                            step_name = STEP_NAMES[node_name]
                            # Send status update
                            yield f"data: {json.dumps({'type': 'status', 'step': step_name, 'node': node_name})}\n\n"
                            await asyncio.sleep(0.05)  # Small delay for UI updates
                    
                    # Collect final state from events
                    if event.get("event") == "on_chain_end" and "data" in event:
                        event_data = event.get("data", {})
                        if isinstance(event_data, dict):
                            if final_state is None:
                                final_state = {}
                            final_state.update(event_data.get("output", {}))
            except Exception as stream_error:
                # Fallback to regular stream if astream_events doesn't work
                print(f"astream_events failed, trying astream: {stream_error}")
                async for chunk in sql_agent_app.astream(state, config):
                    # chunk is a dict with node names as keys
                    for node_name, node_output in chunk.items():
                        if node_name in STEP_NAMES:
                            step_name = STEP_NAMES[node_name]
                            # Send status update
                            yield f"data: {json.dumps({'type': 'status', 'step': step_name, 'node': node_name})}\n\n"
                            await asyncio.sleep(0.05)  # Small delay for UI updates
                    
                    # Update final_state with latest chunk
                    if chunk:
                        # Merge all node outputs into final_state
                        for node_name, node_output in chunk.items():
                            if isinstance(node_output, dict):
                                if final_state is None:
                                    final_state = {}
                                final_state.update(node_output)
            
            # After streaming is complete, get final state
            # If we didn't collect enough state from streaming, invoke once more to get final state
            if final_state is None or not final_state.get('results'):
                # Fallback: invoke synchronously to get final state
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(sql_agent_app.invoke, state, config)
                    final_state = future.result(timeout=60)
            
            # Process final state and send results
            sql_query = final_state.get('sql_query')
            results = final_state.get('results')
            error = final_state.get('error')
            vague_conditions = final_state.get('vague_conditions', [])
            unmatched_warning = final_state.get('unmatched_conditions_warning')
            user_query = final_state.get('user_query', '')
            expanded_query = final_state.get('expanded_query', '')
            
            # Check if vague conditions were detected
            if vague_conditions and len(vague_conditions) > 0:
                explanation = ""
                conversation = final_state.get('conversation', [])
                if conversation:
                    for msg in reversed(conversation):
                        if isinstance(msg, dict):
                            role = msg.get('role', '')
                            content = msg.get('content', '')
                        elif hasattr(msg, 'type'):
                            role = "assistant" if msg.type == "ai" else "user"
                            content = msg.content if hasattr(msg, 'content') else str(msg)
                        elif hasattr(msg, 'content'):
                            role = "assistant"
                            content = msg.content
                        else:
                            continue
                        
                        if role == 'assistant' and content:
                            explanation = content
                            break
                
                yield f"data: {json.dumps({'type': 'result', 'parcels': [], 'summary': explanation or 'Please clarify vague conditions in your query.', 'sql': None, 'session_id': session_id})}\n\n"
                return
            
            if error:
                yield f"data: {json.dumps({'type': 'result', 'parcels': [], 'summary': f'Error: {error}', 'sql': sql_query, 'session_id': session_id})}\n\n"
                return
            
            # Ensure results is a list
            if results is None:
                results = []
            
            # Extract explanation from conversation
            explanation = ""
            conversation = final_state.get('conversation', [])
            if conversation:
                for msg in reversed(conversation):
                    if isinstance(msg, dict):
                        role = msg.get('role', '')
                        content = msg.get('content', '')
                    elif hasattr(msg, 'type'):
                        role = "assistant" if msg.type == "ai" else "user"
                        content = msg.content if hasattr(msg, 'content') else str(msg)
                    elif hasattr(msg, 'content'):
                        role = "assistant"
                        content = msg.content
                    else:
                        continue
                    
                    if role == 'assistant' and content:
                        if "not available in the database" not in content:
                            if content != user_query and content != expanded_query:
                                if not content.startswith(user_query) and not content.startswith(expanded_query):
                                    explanation = content
                                    break
            
            # Convert all geometries to GeoJSON and transform to parcels
            parcels = []
            for row in results:
                if not isinstance(row, dict):
                    row_dict = {}
                    for key, value in row.items():
                        row_dict[key] = value
                    row = row_dict
                else:
                    row = dict(row)
                
                parcel = transform_row_to_parcel(row, explanation)
                if parcel:
                    parcels.append(parcel)
            
            # Generate summary
            if parcels:
                summary = f"Found {len(parcels)} parcel{'s' if len(parcels) != 1 else ''} matching your criteria."
                if explanation and explanation != user_query and explanation != expanded_query:
                    if not explanation.startswith(user_query) and not explanation.startswith(expanded_query):
                        summary += f" {explanation}"
            else:
                summary = "No parcels found matching your criteria."
                if explanation and explanation != user_query and explanation != expanded_query:
                    if not explanation.startswith(user_query) and not explanation.startswith(expanded_query):
                        summary += f" {explanation}"
            
            # Include unmatched conditions warning
            if unmatched_warning:
                if summary:
                    summary = f"{summary}\n\n{unmatched_warning}"
                else:
                    summary = unmatched_warning
            
            # Convert ParcelResponse objects to dictionaries for JSON serialization
            parcels_dict = [parcel.model_dump() if hasattr(parcel, 'model_dump') else parcel.dict() if hasattr(parcel, 'dict') else parcel for parcel in parcels]
            
            # Send final result
            yield f"data: {json.dumps({'type': 'result', 'parcels': parcels_dict, 'summary': summary, 'sql': sql_query, 'session_id': session_id})}\n\n"
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"ERROR in stream_search_parcels: {str(e)}")
            print(f"Traceback: {error_traceback}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@api_app.post("/api/search")
async def search_parcels(request: QueryRequest):
    """Search for parcels using natural language query (streaming version)"""
    print(f"Received POST request to /api/search with query: {request.query}")
    return await stream_search_parcels(request)


@api_app.get("/api/test")
async def test_endpoint():
    """Simple test endpoint to verify routing"""
    return {"message": "API is working", "status": "ok"}

@api_app.post("/api/test")
async def test_post_endpoint():
    """Simple POST test endpoint to verify POST routing"""
    return {"message": "POST is working", "status": "ok"}

@api_app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    error = None
    traceback_str = None
    sql_agent_loaded = False
    
    try:
        # Check environment variables
        env_vars = {
            "DB_HOST": bool(os.getenv("DB_HOST")),
            "DB_USER": bool(os.getenv("DB_USER")),
            "DB_PASSWORD": bool(os.getenv("DB_PASSWORD")),
            "DB_NAME": bool(os.getenv("DB_NAME")),
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "SUPABASE_URL_SESSION": bool(os.getenv("SUPABASE_URL_SESSION")),
            "SUPABASE_PWD": bool(os.getenv("SUPABASE_PWD")),
        }
        
        # Try to import sql_agent
        from sql_agent import app as sql_agent_app
        sql_agent_loaded = True
    except Exception as e:
        import traceback
        sql_agent_loaded = False
        error = str(e)
        traceback_str = traceback.format_exc()
    
    return {
        "status": "ok" if sql_agent_loaded else "error",
        "environment_variables": env_vars if 'env_vars' in locals() else {},
        "sql_agent_loaded": sql_agent_loaded,
        "error": error,
        "traceback": traceback_str
    }


# Catch-all route for non-API paths - return 404
# This must be last to catch all unmatched routes
# Note: We don't include POST or OPTIONS here to avoid conflicts with /api/search
@api_app.get("/", include_in_schema=False)
async def root():
    """Root endpoint"""
    raise HTTPException(status_code=404, detail="Not Found - This API only handles /api/* routes")

@api_app.get("/{path:path}", include_in_schema=False)
@api_app.put("/{path:path}", include_in_schema=False)
@api_app.delete("/{path:path}", include_in_schema=False)
async def catch_all(path: str):
    """Catch-all route that returns 404 for non-API routes"""
    print(f"Catch-all route hit: {path}")
    # Only handle /api/* routes - everything else should go to frontend
    if not path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found - This API only handles /api/* routes")
    raise HTTPException(status_code=404, detail=f"API endpoint not found: /{path}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api_app, host="0.0.0.0", port=8000)

