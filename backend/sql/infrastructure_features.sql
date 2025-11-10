-- infrastructure
CREATE SCHEMA IF NOT EXISTS infrastructure_features;

DROP TABLE IF EXISTS infrastructure_features.infrastructure;
CREATE TABLE infrastructure_features.infrastructure (
    infrastructure_feature_id UUID PRIMARY KEY,
    class character varying(1000) NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL,
    source character varying(1000) NOT NULL,
    operator character varying(1000) NOT NULL,
    voltage integer NOT NULL
);

COMMENT ON COLUMN infrastructure_features.infrastructure.class IS 'Class of the infrastructure feature; values are "substation" or "power_line"';
COMMENT ON COLUMN infrastructure_features.infrastructure.voltage IS 'Unit: volts';

-- transportation
DROP TABLE IF EXISTS infrastructure_features.transportation;
CREATE TABLE infrastructure_features.transportation (
    transportation_feature_id UUID PRIMARY KEY,
    class character varying(1000) NOT NULL,
    geometry geometry(LineString, 4326) NOT NULL,
    geometry_26986 geometry(LineString, 26986) NOT NULL,
    source character varying(1000) NOT NULL
);

COMMENT ON COLUMN infrastructure_features.transportation.class IS 'Class of the transportation feature; values are "motorway", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service", "unknown"';

-- Indexes
CREATE INDEX ON infrastructure_features.infrastructure USING GIST (geometry_26986);
CREATE INDEX ON infrastructure_features.transportation USING GIST (geometry_26986);