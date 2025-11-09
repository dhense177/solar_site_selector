import geopandas as gpd


df = gpd.read_file('data/boundaries/massachusetts_town_boundaries/TOWNSSURVEY_POLY.shp')

df = df.to_crs('EPSG:4326')

df.to_parquet('s3://solar-parcel-finder/data/boundaries/massachusetts_municipalities.parquet')