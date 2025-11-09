from sqlalchemy import text
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping as shapely_mapping
import json

def run_query(sql: str, con):
    try:
        print(f'Query being run: {sql} \n\n')
        results = con.execute(text(sql)).mappings().all()
        
        # Convert PostGIS geometry objects to GeoJSON for serialization
        converted_results = []
        for row in results:
            row_dict = dict(row)
            # Check if geometry column exists and convert it
            if 'geometry' in row_dict and row_dict['geometry'] is not None:
                geom = row_dict['geometry']
                # If it's already a string (hex WKB), leave it as-is for api_server to handle
                # If it's a PostGIS object, convert to GeoJSON
                if not isinstance(geom, str):
                    try:
                        shapely_geom = to_shape(geom)
                        geo_json = shapely_mapping(shapely_geom)
                        # Convert tuples to lists
                        row_dict['geometry'] = json.loads(json.dumps(geo_json))
                    except:
                        # If conversion fails, keep original
                        pass
            converted_results.append(row_dict)
        
        return converted_results, None
    except Exception as e:
        print("Error running query: ", str(e))
        return None, str(e)


def create_reprojected_geometry_col(gdf, geometry_col, new_geometry_col, srid):
    gdf[new_geometry_col] = gdf[geometry_col]
    gdf = gdf.set_geometry(new_geometry_col)
    gdf = gdf.to_crs(srid)
    gdf = gdf.set_geometry(geometry_col)
    return gdf