CREATE SCHEMA IF NOT EXISTS geographic_features;
-- land cover
DROP TABLE IF EXISTS geographic_features.land_cover;
CREATE TABLE geographic_features.land_cover (
    land_cover_feature_id UUID PRIMARY KEY,
    class character varying(1000) NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL,
    source character varying(1000) NOT NULL
);

COMMENT ON COLUMN geographic_features.land_cover.class IS 'Class of the land cover feature; values are "wetland" or "forest"';

-- land use
DROP TABLE IF EXISTS geographic_features.land_use;
CREATE TABLE geographic_features.land_use (
    land_use_feature_id UUID PRIMARY KEY,
    class character varying(1000) NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL,
    source character varying(1000) NOT NULL
);

COMMENT ON COLUMN geographic_features.land_use.class IS 'Class of the land use feature; values are "industrial", "commercial", "retail", "residential", "farmland", "farmyard", "brownfield", "greenfield", "meadow", "quarry", "landfill", "national_park", "species_management_area", "strict_nature_reserve", "wilderness_area"';


-- flood zones
-- DROP TABLE IF EXISTS geographic_features.flood_zones;
-- CREATE TABLE geographic_features.flood_zones (
--     flood_zone_id character varying(1000) PRIMARY KEY,
--     category character varying(1000) NOT NULL,
--     geometry geometry(Geometry, 4326) NOT NULL,
--     geometry_26986 geometry(Geometry, 26986) NOT NULL
-- );

-- COMMENT ON TABLE geographic_features.flood_zones IS 'FEMA Flood Zones';

-- open spaces
DROP TABLE IF EXISTS geographic_features.open_spaces;
CREATE TABLE geographic_features.open_spaces (
    open_space_id character varying(1000) PRIMARY KEY,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL
);

COMMENT ON TABLE geographic_features.open_spaces IS 'The protected and recreational open space datalayer contains the boundaries of conservation lands and outdoor recreational facilities in Massachusetts';

-- priority habitats
DROP TABLE IF EXISTS geographic_features.priority_habitats;
CREATE TABLE geographic_features.priority_habitats (
    priority_habitat_id character varying(1000) PRIMARY KEY,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL
);

COMMENT ON TABLE geographic_features.priority_habitats IS 'Priority habitats for rare and endangered species in Massachusetts';

-- prime farmland soils
DROP TABLE IF EXISTS geographic_features.prime_farmland_soils;
CREATE TABLE geographic_features.prime_farmland_soils (
    prime_soil_id character varying(1000) PRIMARY KEY,
    geometry geometry(Geometry, 4326) NOT NULL,
    geometry_26986 geometry(Geometry, 26986) NOT NULL
);

COMMENT ON TABLE geographic_features.prime_farmland_soils IS 'The prime farmland soils datalayer contains the boundaries of prime farmland soils in Massachusetts';

-- Indexes
CREATE INDEX ON geographic_features.land_cover USING GIST (geometry_26986);
CREATE INDEX ON geographic_features.land_use USING GIST (geometry_26986);
-- CREATE INDEX ON geographic_features.flood_zones USING GIST (geometry_26986);
CREATE INDEX ON geographic_features.open_spaces USING GIST (geometry_26986);
CREATE INDEX ON geographic_features.priority_habitats USING GIST (geometry_26986);
CREATE INDEX ON geographic_features.prime_farmland_soils USING GIST (geometry_26986);