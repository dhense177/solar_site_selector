

from sqlalchemy import create_engine
import dotenv
import duckdb
import boto3
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from processing.parcel_processor import process_parcels
from processing.omf_data_processor import create_all_omf_tables, extract_environmental_features, extract_landuse, extract_infrastructure, extract_transportation
from processing.environmental_data_processor import process_fema_flood_zones, process_protected_open_spaces, process_priority_habitats, process_prime_soils

dotenv.load_dotenv()

db_host = os.getenv("DB_HOST", "local")
if db_host == "local":
    user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]
    engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}")
else:
    subase_connection_string = os.getenv("SUPABASE_URL_SESSION")
    engine = create_engine(subase_connection_string)



con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
con.execute("INSTALL httpfs; LOAD httpfs;")

# Configure S3 credentials if needed
session = boto3.Session()
credentials = session.get_credentials()

if credentials:
    access_key = credentials.access_key
    secret_key = credentials.secret_key
con.execute(f"SET s3_access_key_id = '{access_key}'")
con.execute(f"SET s3_secret_access_key = '{secret_key}'")


create_all_omf_tables(con)

# Check if only populating geographic_features
parcels_only = os.getenv("RECREATE_PARCELS", "false").lower() == "true"
geographic_features_only = os.getenv("RECREATE_GEO_FEATURES", "false").lower() == "true"
infra_features_only = os.getenv("RECREATE_INFRA_FEATURES", "false").lower() == "true"

# Parcels
if parcels_only:
    print("** Populating parcels table **")
    file_path = 'data/Statewide_parcels_SHP'
    gdf_join = process_parcels(file_path)
    gdf_join.to_postgis(
        name="parcel_details",
        con=engine,
        schema="parcels",
        if_exists="append",
        index=False
    )


if geographic_features_only:
    # Land Cover Features
    print("** Populating geographic features tables **")

    print("** Populating land cover features **")
    gdf_join = extract_environmental_features(con)
    gdf_join.to_postgis(
        name="land_cover",
        con=engine,
        schema="geographic_features",
        if_exists="append",
        index=False
    )

    # Land Use Features
    print("** Populating land use features **")
    gdf_join = extract_landuse(con)
    gdf_join.to_postgis(
        name="land_use",
        con=engine,
        schema="geographic_features",
        if_exists="append",
        index=False
    )

    # Protected Open Spaces
    print("** Populating protected open spaces **")
    gdf_join = process_protected_open_spaces()
    gdf_join.to_postgis(
        name="open_spaces",
        con=engine,
        schema="geographic_features",
        if_exists="append",
        index=False
    )

    # FEMA Flood Zones
    # print("** Populating FEMA flood zones **")
    # gdf_join = process_fema_flood_zones()
    # gdf_join.to_postgis(
    #     name="flood_zones",
    #     con=engine,
    #     schema="geographic_features",
    #     if_exists="append",
    #     index=False
    # )

    # Priority Habitats
    print("** Populating priority habitats **")
    gdf_join = process_priority_habitats()
    gdf_join.to_postgis(
        name="priority_habitats",
        con=engine,
        schema="geographic_features",
        if_exists="append",
        index=False
    )

    # Prime Farmland Soils
    print("** Populating prime farmland soils **")
    gdf_join = process_prime_soils()
    gdf_join.to_postgis(
        name="prime_farmland_soils",
        con=engine,
        schema="geographic_features",
        if_exists="append",
        index=False
    )


if infra_features_only:
    print("** Populating infrastructure tables **")


    # Infrastructure Features
    print("** Populating infrastructure features **")
    gdf_join = extract_infrastructure(con)
    gdf_join.to_postgis(
        name="infrastructure",
        con=engine,
        schema="infrastructure_features",
        if_exists="append",
        index=False
    )

    # Transportation Features
    print("** Populating transportation features **")
    gdf_join = extract_transportation(con)
    gdf_join.to_postgis(
        name="transportation",
        con=engine,
        schema="infrastructure_features",
        if_exists="append",
        index=False
    )
