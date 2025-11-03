

def create_reprojected_geometry_col(gdf, geometry_col, new_geometry_col, srid):
    gdf[new_geometry_col] = gdf[geometry_col]
    gdf = gdf.set_geometry(new_geometry_col)
    gdf = gdf.to_crs(srid)
    gdf = gdf.set_geometry(geometry_col)
    return gdf