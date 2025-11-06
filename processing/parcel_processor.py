import geopandas as gpd
import pandas as pd
import dotenv
import os
import fiona
from sqlalchemy import create_engine
from db_actions.db_utils import create_reprojected_geometry_col
dotenv.load_dotenv()

user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]

engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}")


def create_full_address(df):
    df['full_address'] = df['OWN_ADDR'].fillna('') + ' ' + df['OWN_CITY'].fillna('') + ' ' + df['OWN_STATE'].fillna('') + ' ' + df['OWN_ZIP'].fillna('') + ' USA'

    df['full_address'] = df['full_address'].apply(lambda x: ' '.join(x.strip() for x in x.split()))
    return df


def read_parcels(file_path):
# '/Users/davidhenslovitz/Downloads/Statewide_parcels_SHP/L3_TAXPAR_POLY_ASSESS_EAST.shp'
    df_parcels_east = gpd.read_file(f"{file_path}/L3_TAXPAR_POLY_ASSESS_EAST.shp")

    df_parcels_west = gpd.read_file(f"{file_path}/L3_TAXPAR_POLY_ASSESS_WEST.shp")

    # #*** For testing: limit rows
    # df_parcels_west = df_parcels_west.iloc[:10]
    # #*** #
    return df_parcels_east, df_parcels_west


def concatenate_east_west(df_parcels_east, df_parcels_west):
    gdf = gpd.GeoDataFrame(pd.concat([df_parcels_east, df_parcels_west], ignore_index=True))
    gdf = gdf.to_crs('EPSG:4326')
    return gdf

def get_county_boundaries():
    df_county = gpd.read_parquet('s3://solar-parcel-finder/data/boundaries/massachusetts_municipalities.parquet')
    df_county = df_county.to_crs('EPSG:4326')
    df_county = df_county[['TOWN', 'COUNTY', 'geometry']].rename(columns={'TOWN': 'municipality_name', 'COUNTY': 'county_name'})
    return df_county

def create_area_columns(gdf):
    gdf = gdf.to_crs('EPSG:5070')
    gdf['area_m2'] = gdf['geometry'].area
    gdf['area_acres'] = gdf['area_m2'] * 0.000247105
    gdf = gdf.to_crs('EPSG:4326')
    return gdf

def join_with_county_boundaries(gdf):
    df_county = get_county_boundaries()
    gdf_join = gpd.sjoin(gdf, df_county, how='inner', predicate='within')
    gdf_join = gdf_join.drop(columns=["index_right"])
    return gdf_join


def is_numeric(val):
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False



def read_process_suitable_parcels():
    gdb_path = "data/mass_parcel_suitability.gdb"
    layers = fiona.listlayers(gdb_path)
    gdf = gpd.read_file(gdb_path, layer=layers[0])

    gdf['R_GM_CapKW'] = gdf['R_GM_CapKW'].apply(lambda x: float(x.replace(",","")) if is_numeric(x.replace(",","")) else 0.0)

    # Filter for parcels with Ground Mounted Capacity > 5 MW (5000 kW) which is the minimum capacity for a solar farm
    gdf = gdf[gdf['R_GM_CapKW'] > 5000].reset_index(drop=True)

    # Filter for prime parcels only
    gdf = gdf[gdf['MainScore'].isin(['All A', 'Mostly A'])].reset_index(drop=True)
    gdf = gdf.to_crs('EPSG:4326')

    cols_to_keep = ['geometry','R_GM_CapKW']
    gdf = gdf[cols_to_keep].rename(columns={'R_GM_CapKW': 'ground_mounted_capacity_kw'})

    gdf["geometry"] = gdf.geometry.centroid

    return gdf

def process_parcels(file_path):
    df_parcels_east, df_parcels_west = read_parcels(file_path)
    df_parcels_east = create_full_address(df_parcels_east)
    df_parcels_west = create_full_address(df_parcels_west)

    # Filter out unneccessary columns
    cols_to_keep = ['full_address', 'geometry']
    df_parcels_east = df_parcels_east[cols_to_keep]
    df_parcels_west = df_parcels_west[cols_to_keep]

    gdf = concatenate_east_west(df_parcels_east, df_parcels_west)

    gdf = create_area_columns(gdf)

    gdf['parcel_id'] = gdf.index+1
    gdf_join = join_with_county_boundaries(gdf)

    gdf_join = gdf_join[gdf_join['parcel_id'].duplicated()==False].reset_index(drop=True)
    gdf_join['source'] = 'MASSGIS'

    gdf_vetted = read_process_suitable_parcels()
    gdf_join = gpd.sjoin(gdf_join, gdf_vetted, how='inner', predicate='contains')

    gdf_join = gdf_join.drop(columns=['index_right'])

    # Remove duplicates arising from the join with the vetted parcels
    gdf_join = gdf_join[gdf_join['parcel_id'].duplicated()==False].reset_index(drop=True)

    # Create new column with reprojection to 26986
    gdf_join = create_reprojected_geometry_col(gdf_join,'geometry','geometry_26986','26986')

    return gdf_join