import geopandas as gpd
from sqlalchemy import create_engine
import psycopg2
import os
import dotenv

dotenv.load_dotenv()

user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]

# Check if only recreating geographic_features
GEOGRAPHIC_FEATURES = os.getenv("RECREATE_GEO_FEATURES", "false").lower() == "true"
INFRASTRUCTURE_FEATURES = os.getenv("RECREATE_INFRA_FEATURES", "false").lower() == "true"
PARCELS = os.getenv("RECREATE_PARCELS", "false").lower() == "true"

# --- (Re)create DB ---
if GEOGRAPHIC_FEATURES and INFRASTRUCTURE_FEATURES and PARCELS:
    print("** Recreating Database **")
    conn = psycopg2.connect(dbname="postgres", user=user, password=password, host=host, port=port)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Terminate all active sessions to the target database
    print(f"Terminating all active sessions to {db_name}...")
    cur.execute("""
        SELECT pg_terminate_backend(pid) 
        FROM pg_stat_activity 
        WHERE datname = %s AND pid <> pg_backend_pid();
    """, (db_name,))
    terminated_sessions = cur.fetchall()
    terminated_count = len(terminated_sessions)
    print(f"Terminated {terminated_count} active session(s)")
    
    cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
    cur.execute(f"CREATE DATABASE {db_name};")
    cur.close()
    conn.close()

    # --- Enable PostGIS ---
    conn = psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    conn.commit()
    cur.close()
    conn.close()

# --- Create Schemas & Tables ---
conn = psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port)
cur = conn.cursor()

# Recreate geographic_features tables
if GEOGRAPHIC_FEATURES:
    print("** Recreating geographic_features tables **")
    sql_geographic_features = "sql/geographic_features.sql"
    with open(sql_geographic_features, "r") as f:
        sql = f.read()
    cur.execute(sql)

if PARCELS:
    print("** Recreating parcels tables **")
    sql_parcels = "sql/parcels.sql"
    with open(sql_parcels, "r") as f:
        sql = f.read()
    cur.execute(sql)

if INFRASTRUCTURE_FEATURES:
    print("** Recreating infrastructure tables **")
    sql_infrastructure = "sql/infrastructure_features.sql"
    with open(sql_infrastructure, "r") as f:
        sql = f.read()
    cur.execute(sql)

conn.commit()
cur.close()
conn.close()