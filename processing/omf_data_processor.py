import duckdb
from shapely import wkt
import geopandas as gpd
from tqdm import tqdm
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
import pyarrow.dataset as ds
import boto3
import dotenv
import os
from sqlalchemy import create_engine
from db_actions.db_utils import create_reprojected_geometry_col
dotenv.load_dotenv()

user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]

engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}")

# Massachusets State Bounding Box
xmin = -73.507239199792
ymin = 41.23908260581605
xmax = -69.92871308883089
ymax = 42.88675909238091

latest_release = '2025-09-24.0'

def create_land_cover_table(con):
    con.execute("SET s3_region = 'us-west-2'")
    con.execute(f"""
    CREATE TABLE land_cover AS (
        SELECT
            id,
            (sources->0->>'dataset') as source,
            ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry,
            subtype AS class
        FROM read_parquet('s3://overturemaps-us-west-2/release/{latest_release}/theme=base/type=land_cover/*.parquet')
        WHERE bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
    """)

def create_land_use_table(con):
    con.execute("SET s3_region = 'us-west-2'")
    con.execute(f"""
    CREATE TABLE land_use AS (
        SELECT
            id,
            (sources->0->>'dataset') as source,
            ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry,
            class
        FROM read_parquet('s3://overturemaps-us-west-2/release/{latest_release}/theme=base/type=land_use/*.parquet')
        WHERE bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
    """)

def create_infrastructure_table(con):
    con.execute("SET s3_region = 'us-west-2'")
    con.execute(f"""
    CREATE TABLE infrastructure AS (
        SELECT
            id,
            (sources->0->>'dataset') as source,
            ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry,
            class,
            (source_tags->>'operator') as operator,
            (source_tags->>'voltage') as voltage
        FROM read_parquet('s3://overturemaps-us-west-2/release/{latest_release}/theme=base/type=infrastructure/*.parquet')
        WHERE bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
    """)


def create_transportation_table(con):
    con.execute("SET s3_region = 'us-west-2'")
    con.execute(f"""
    CREATE TABLE transportation AS (
        SELECT
            id,
            (sources->0->>'dataset') as source,
            ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry,
            subtype,
            class
        FROM read_parquet('s3://overturemaps-us-west-2/release/{latest_release}/theme=transportation/type=segment/*.parquet')
        WHERE bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
    """)

def create_all_omf_tables(con):
    create_land_cover_table(con)
    create_land_use_table(con)
    create_infrastructure_table(con)
    create_transportation_table(con)


def extract_environmental_features(con):
    query = f"""

    SELECT
        id AS land_cover_feature_id,
        class,
        source,
        ST_AsText(geometry) AS geometry,
    FROM land_cover
    WHERE class IN ('wetland', 'forest')
    """

    df = con.execute(query).fetchdf()
    # df['geometry_4326'] = df['geometry']
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry',crs='EPSG:4326')
    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf



def extract_landuse(con):
    query = f"""

    SELECT
        id AS land_use_feature_id,
        class,
        source,
        ST_AsText(geometry) AS geometry,
    FROM land_use
    WHERE class IN ('industrial', 'commercial', 'retail', 'residential', 'farmland', 'farmyard', 'brownfield', 'greenfield', 'meadow', 'quarry', 'landfill', 'national_park', 'species_management_area', 'strict_nature_reserve', 'wilderness_area')
    """
    df = con.execute(query).fetchdf()
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry',crs='EPSG:4326')
    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf

def extract_infrastructure(con):
    query = f"""

    SELECT
        id AS infrastructure_feature_id,
        class,
        source,
        operator,
        voltage,
        ST_AsText(geometry) AS geometry,
    FROM infrastructure
    WHERE class IN ('substation', 'power_line')
    """
    df = con.execute(query).fetchdf()

    # Remove nulls and 'medium' value in voltage column
    df = df[(df['voltage'].isnull()==False)&(df['voltage']!='medium')&(df['operator'].isnull()==False)].reset_index(drop=True)
    
    # Only keep first voltage number where multiple exist
    df['voltage'] = df['voltage'].apply(lambda x: int(x.split(';')[0]))
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry',crs='EPSG:4326')

    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf

def extract_transportation(con):
    query = f"""

    SELECT
        id AS transportation_feature_id,
        class,
        source,
        ST_AsText(geometry) AS geometry,
    FROM transportation
    WHERE subtype = 'road'
    AND class IN ('motorway', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'living_street', 'service', 'unknown')
    """
    df = con.execute(query).fetchdf()
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry',crs='EPSG:4326')

    gdf = create_reprojected_geometry_col(gdf,'geometry','geometry_26986','26986')
    return gdf