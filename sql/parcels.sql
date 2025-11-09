-- parcels
CREATE SCHEMA IF NOT EXISTS parcels;

DROP TABLE IF EXISTS parcels.parcel_details;
CREATE TABLE parcels.parcel_details (
    parcel_id character varying(1000) PRIMARY KEY,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL,
    full_address character varying(1000) NOT NULL,
    owner_name character varying(1000),
    total_value numeric,
    county_name character varying(1000) NOT NULL,
    municipality_name character varying(1000) NOT NULL,
    area_m2 numeric NOT NULL,
    area_acres numeric NOT NULL,
    source character varying(1000) NOT NULL,
    ground_mounted_capacity_kw numeric NOT NULL
);

COMMENT ON COLUMN parcels.parcel_details.parcel_id IS 'Unique identifier for the parcel (UUID)';
COMMENT ON COLUMN parcels.parcel_details.geometry IS 'PostGIS geometry column storing the parcel boundary (MULTIPOLYGON in EPSG:4326)';
COMMENT ON COLUMN parcels.parcel_details.full_address IS 'Complete street address of the parcel';
COMMENT ON COLUMN parcels.parcel_details.owner_name IS 'Name of the owner of the parcel';
COMMENT ON COLUMN parcels.parcel_details.total_value IS 'Total value of the parcel in dollars';
COMMENT ON COLUMN parcels.parcel_details.county_name IS 'UPPERCASE county name (no suffix "County"). Examples: "WORCESTER", "NORFOLK"';
COMMENT ON COLUMN parcels.parcel_details.municipality_name IS 'UPPERCASE municipality name. Examples: "BARRE", "FRANKLIN"';
COMMENT ON COLUMN parcels.parcel_details.area_m2 IS 'Area of the parcel in square meters';
COMMENT ON COLUMN parcels.parcel_details.area_acres IS 'Area of the parcel in acres';
COMMENT ON COLUMN parcels.parcel_details.source IS 'Source dataset or data provider for this parcel';
COMMENT ON COLUMN parcels.parcel_details.ground_mounted_capacity_kw IS 'Ground-mounted solar capacity in kilowatts';

-- Indexes
CREATE INDEX ON parcels.parcel_details USING GIST (geometry_26986);