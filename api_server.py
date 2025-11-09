"""
FastAPI server for integrating sql_agent.py with the frontend
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from sql_agent import app as sql_agent_app
from langchain_core.runnables import RunnableConfig
from shapely.geometry import mapping as shapely_mapping
from geoalchemy2.shape import to_shape
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Initialize FastAPI app
api_app = FastAPI(title="Solar Parcel Search API")

# Add error handler for debugging
@api_app.exception_handler(Exception)
async def global_exception_handler(request, exc):
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
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
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


@api_app.post("/api/search", response_model=SearchResponse)
async def search_parcels(request: QueryRequest):
    """Search for parcels using natural language query"""
    try:
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
        
        # Invoke SQL agent with timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(sql_agent_app.invoke, state, config)
                final_state = future.result(timeout=60)
        except FuturesTimeoutError:
            raise HTTPException(status_code=504, detail="Query timed out after 60 seconds")
        
        # Extract results
        sql_query = final_state.get('sql_query')
        results = final_state.get('results', [])
        error = final_state.get('error')
        
        if error:
            return SearchResponse(
                parcels=[],
                summary=f"Error: {error}",
                sql=sql_query,
                session_id=session_id
            )
        
        # Extract explanation from conversation
        explanation = ""
        conversation = final_state.get('conversation', [])
        if conversation:
            for msg in reversed(conversation):
                if isinstance(msg, dict) and msg.get('role') == 'assistant':
                    explanation = msg.get('content', '')
                    break
        
        # Convert all geometries to GeoJSON and transform to parcels
        parcels = []
        for row in results:
            # Convert RowMapping to dict, preserving geometry object
            if not isinstance(row, dict):
                row_dict = {}
                for key, value in row.items():
                    row_dict[key] = value
                row = row_dict
            else:
                row = dict(row)  # Make a copy
            
            parcel = transform_row_to_parcel(row, explanation)
            if parcel:
                parcels.append(parcel)
        
        # Generate summary
        if parcels:
            summary = f"Found {len(parcels)} parcel{'s' if len(parcels) != 1 else ''} matching your criteria."
            if explanation:
                summary += f" {explanation}"
        else:
            summary = "No parcels found matching your criteria."
            if explanation:
                summary += f" {explanation}"
        
        return SearchResponse(
            parcels=parcels,
            summary=summary,
            sql=sql_query,
            session_id=session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api_app, host="0.0.0.0", port=8000)

