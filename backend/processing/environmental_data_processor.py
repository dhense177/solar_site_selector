import geopandas as gpd
from db_actions.db_utils import create_reprojected_geometry_col

def process_fema_flood_zones():
    gdb_path = "data/nfhl/FEMA_NFHL_POLY.shp"
    gdf = gpd.read_file(gdb_path)
    gdf = gdf.to_crs('EPSG:4326')

    gdf['flood_zone_id'] = gdf.index+1

    gdf = gdf[['flood_zone_id','LABEL','geometry']].rename(columns={'LABEL':'category'})

    gdf = gdf[gdf['category'].isin(['1% Annual Chance Flood Hazard','0.2% Annual Chance Flood Hazard','Regulatory Floodway'])].reset_index(drop=True)

    gdf = gdf[gdf['geometry'].isnull()==False].reset_index(drop=True)

    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf

def process_protected_open_spaces():
    gdb_path = "data/openspace/OPENSPACE_POLY.shp"
    gdf = gpd.read_file(gdb_path)
    gdf = gdf.to_crs('EPSG:4326')

    gdf['open_space_id'] = gdf.index+1
    gdf = gdf[['open_space_id','geometry']]

    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf

def process_priority_habitats():
    gdb_path = "data/prihab/PRIHAB_POLY.shp"
    gdf = gpd.read_file(gdb_path)
    gdf = gdf.to_crs('EPSG:4326')

    gdf = gdf[['PRIHAB_ID','geometry']].rename(columns={'PRIHAB_ID': 'priority_habitat_id'})

    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf

def process_prime_soils():
    gdb_path = "data/Prime_Farmland_Soils/Prime_Farmland_Soils_(Feature_Service).shp"
    gdf = gpd.read_file(gdb_path)
    gdf = gdf.to_crs('EPSG:4326')
    gdf = gdf[['OBJECTID','geometry']].rename(columns={'OBJECTID': 'prime_soil_id'})
    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf