import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Polygon, Popup, useMap } from "react-leaflet";
import { LatLngExpression, LatLngBounds, LatLngTuple } from "leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

// Fix Leaflet default icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface Parcel {
  address: string;
  county: string;
  acreage: number;
  explanation: string;
  geometry: {
    type: string;
    coordinates: number[][][] | number[][][][];
  };
}

interface MapViewProps {
  parcels: Parcel[];
  selectedParcel?: Parcel | null;
}

// Convert GeoJSON coordinates to Leaflet LatLng format
// GeoJSON uses [lng, lat] format, Leaflet needs [lat, lng]
function geoJsonToLeaflet(coordinates: number[][][] | number[][][][]): LatLngExpression[][] {
  if (coordinates.length === 0) return [];
  
  try {
    // Handle MultiPolygon: coordinates[][][][]
    if (Array.isArray(coordinates[0]) && Array.isArray(coordinates[0][0]) && Array.isArray(coordinates[0][0][0])) {
      const multiPolygon = coordinates as number[][][][];
      return multiPolygon.flatMap(polygon => 
        polygon.map(ring => 
          ring.map((coord) => {
            // GeoJSON: [lng, lat] -> Leaflet: [lat, lng]
            const [lng, lat] = coord;
            if (typeof lng === 'number' && typeof lat === 'number' && !isNaN(lat) && !isNaN(lng)) {
              return [lat, lng] as LatLngExpression;
            }
            return null;
          }).filter((pos): pos is LatLngExpression => pos !== null)
        )
      );
    }
    
    // Handle Polygon: coordinates[][][]
    if (Array.isArray(coordinates[0]) && Array.isArray(coordinates[0][0])) {
      const polygon = coordinates as number[][][];
      return polygon.map(ring => 
        ring.map((coord) => {
          // GeoJSON: [lng, lat] -> Leaflet: [lat, lng]
          const [lng, lat] = coord;
          if (typeof lng === 'number' && typeof lat === 'number' && !isNaN(lat) && !isNaN(lng)) {
            return [lat, lng] as LatLngExpression;
          }
          return null;
        }).filter((pos): pos is LatLngExpression => pos !== null)
      );
    }
  } catch (error) {
    console.error('Error converting GeoJSON to Leaflet format:', error);
  }
  
  return [];
}

// Component to handle map view updates when parcels change
function MapUpdater({ parcels, selectedParcel }: { parcels: Parcel[]; selectedParcel?: Parcel | null }) {
  const map = useMap();

  useEffect(() => {
    // Skip if map isn't initialized yet
    if (!map) return;

    // Skip if we have a selected parcel (let that effect handle it)
    if (selectedParcel) return;

    if (parcels.length > 0) {
      // Collect all coordinates from parcels
      const allCoordinates: LatLngTuple[] = [];
      
      parcels.forEach(parcel => {
        if (parcel.geometry && parcel.geometry.coordinates) {
          try {
            const positions = geoJsonToLeaflet(parcel.geometry.coordinates);
            positions.forEach(ring => {
              ring.forEach(pos => {
                if (Array.isArray(pos) && pos.length >= 2) {
                  const lat = typeof pos[0] === 'number' ? pos[0] : parseFloat(String(pos[0]));
                  const lng = typeof pos[1] === 'number' ? pos[1] : parseFloat(String(pos[1]));
                  if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
                    allCoordinates.push([lat, lng]);
                  }
                }
              });
            });
          } catch (e) {
            console.warn('Error processing parcel geometry:', e);
          }
        }
      });
      
      if (allCoordinates.length > 0) {
        try {
          // Create bounds using Leaflet's LatLngBounds
          const bounds = new LatLngBounds(allCoordinates);
          
          // Use a small timeout to ensure map container is fully rendered
          const timeoutId = setTimeout(() => {
            try {
              map.fitBounds(bounds, {
                padding: [50, 50],
                maxZoom: 16,
                animate: true
              });
            } catch (e) {
              console.error('Error fitting bounds:', e);
            }
          }, 300);
          
          return () => clearTimeout(timeoutId);
        } catch (e) {
          console.error('Error creating bounds:', e);
        }
      }
    } else {
      // Default to Massachusetts view when no parcels
      map.setView([42.2373, -71.5314], 8, { animate: true });
    }
  }, [parcels, map, selectedParcel]);

  useEffect(() => {
    if (!map || !selectedParcel) return;
    
    if (selectedParcel.geometry && selectedParcel.geometry.coordinates) {
      try {
        const positions = geoJsonToLeaflet(selectedParcel.geometry.coordinates);
        if (positions.length > 0 && positions[0].length > 0) {
          const center = positions[0][0];
          map.setView(center, 14, { animate: true });
        }
      } catch (e) {
        console.error('Error setting view for selected parcel:', e);
      }
    }
  }, [selectedParcel, map]);

  return null;
}

const MapView = ({ parcels, selectedParcel }: MapViewProps) => {
  // Default center: Massachusetts (approximately center of the state)
  const defaultCenter: [number, number] = [42.2373, -71.5314];
  const defaultZoom = 8;
  
  // Basemap toggle state
  const [mapType, setMapType] = useState<"map" | "satellite">("map");

  // Render parcel polygons - simplified and more robust
  const parcelPolygons = useMemo(() => {
    if (!parcels || parcels.length === 0) {
      console.log('MapView: No parcels to render');
      return [];
    }
    
    console.log(`MapView: Processing ${parcels.length} parcels`);
    console.log('MapView: First parcel sample:', {
      hasGeometry: !!parcels[0]?.geometry,
      geometryType: parcels[0]?.geometry?.type,
      hasCoordinates: !!parcels[0]?.geometry?.coordinates,
      coordinatesLength: parcels[0]?.geometry?.coordinates?.length
    });
    
    const polygons: Array<{
      key: string;
      parcel: Parcel;
      positions: LatLngExpression[][];
      isSelected: boolean;
    }> = [];
    
    parcels.forEach((parcel, index) => {
      // Skip if no geometry
      if (!parcel.geometry || !parcel.geometry.coordinates) {
        console.warn(`MapView: Parcel ${index} has no geometry`, {
          address: parcel.address,
          hasGeometry: !!parcel.geometry,
          geometry: parcel.geometry
        });
        return;
      }

      try {
        console.log(`MapView: Processing parcel ${index} geometry:`, {
          geometryType: parcel.geometry.type,
          coordinatesType: Array.isArray(parcel.geometry.coordinates) ? 'array' : typeof parcel.geometry.coordinates,
          coordinatesLength: Array.isArray(parcel.geometry.coordinates) ? parcel.geometry.coordinates.length : 'N/A'
        });
        
        const positions = geoJsonToLeaflet(parcel.geometry.coordinates);
        
        console.log(`MapView: Converted to Leaflet positions:`, {
          positionsLength: positions.length,
          firstRingLength: positions[0]?.length,
          firstPoint: positions[0]?.[0]
        });
        
        // Validate positions
        if (!positions || positions.length === 0) {
          console.error(`MapView: Parcel ${index} has invalid positions after conversion`, {
            coordinates: parcel.geometry.coordinates
          });
          return;
        }
        
        const firstRing = positions[0];
        if (!firstRing || firstRing.length < 3) {
          console.error(`MapView: Parcel ${index} first ring has insufficient points: ${firstRing?.length}`, {
            positions: positions
          });
          return;
        }
        
        // Create stable key
        const parcelKey = parcel.address || `parcel-${index}`;
        
        polygons.push({
          key: `${parcelKey}-${index}`,
          parcel,
          positions,
          isSelected: selectedParcel === parcel
        });
        
        console.log(`MapView: Successfully added polygon for parcel ${index}`);
      } catch (error) {
        console.error(`MapView: Error rendering parcel ${index}:`, error, {
          geometry: parcel.geometry
        });
        return;
      }
    });
    
    console.log(`MapView: Total polygons to render: ${polygons.length}`);
    return polygons;
  }, [parcels, selectedParcel]);

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden" style={{ minHeight: "400px", height: "100%" }}>
      {/* Basemap Toggle - Top Right Corner */}
      <div className="absolute top-2 right-2 z-[1000] bg-white rounded-md shadow-lg p-2 border">
        <RadioGroup value={mapType} onValueChange={(value) => setMapType(value as "map" | "satellite")}>
          <div className="flex items-center space-x-2">
            <RadioGroupItem value="map" id="map" />
            <Label htmlFor="map" className="text-sm cursor-pointer">Map</Label>
          </div>
          <div className="flex items-center space-x-2 mt-1">
            <RadioGroupItem value="satellite" id="satellite" />
            <Label htmlFor="satellite" className="text-sm cursor-pointer">Satellite</Label>
          </div>
        </RadioGroup>
      </div>
      
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        style={{ height: "100%", width: "100%", minHeight: "400px", zIndex: 0 }}
        scrollWheelZoom={true}
        zoomControl={true}
        key={mapType} // Force remount when map type changes
        whenReady={() => {
          console.log("Map container is ready, parcels:", parcels.length);
        }}
      >
        {mapType === "map" ? (
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://www.mass.gov/massgis">MassGIS</a>'
            url="https://tiles.arcgis.com/tiles/hGdibHYSPO59RG1h/arcgis/rest/services/orthos2023/MapServer/tile/{z}/{y}/{x}"
            maxZoom={20}
            minZoom={7}
          />
        )}
        
        <MapUpdater parcels={parcels} selectedParcel={selectedParcel} />
        
        {parcelPolygons.length > 0 ? (
          parcelPolygons.map((polygonData) => {
            const { key, parcel, positions, isSelected } = polygonData;
            
            if (!positions || positions.length === 0) {
              console.warn(`MapView: Polygon ${key} has no positions`);
              return null;
            }
            
            console.log(`MapView: Rendering polygon ${key} with ${positions.length} rings`);
            
            return (
              <Polygon
                key={key}
                positions={positions}
                pathOptions={{
                  color: "#FFB300",
                  fillColor: "#FFB300",
                  fillOpacity: isSelected ? 0.4 : 0.3,
                  weight: isSelected ? 3 : 2,
                }}
                eventHandlers={{
                  add: () => {
                    console.log(`MapView: Polygon ${key} added to map`);
                  }
                }}
              >
                <Popup>
                  <div className="p-2">
                    <h3 className="font-semibold text-sm mb-1">{parcel.address || "Unknown Address"}</h3>
                    <p className="text-xs text-muted-foreground">
                      <strong>County:</strong> {parcel.county || "Unknown"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      <strong>Acres:</strong> {parcel.acreage?.toFixed(2) || "0.00"}
                    </p>
                  </div>
                </Popup>
              </Polygon>
            );
          })
        ) : (
          parcels.length > 0 && (
            <div style={{ position: 'absolute', top: '10px', left: '10px', zIndex: 1000, background: 'white', padding: '10px', borderRadius: '5px' }}>
              <p style={{ color: 'red', fontSize: '12px' }}>No polygons to render. Check console for details.</p>
            </div>
          )
        )}
      </MapContainer>
    </div>
  );
};

export default MapView;
