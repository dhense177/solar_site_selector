import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MapPin, Ruler } from "lucide-react";

interface Parcel {
  address: string;
  county: string;
  acreage: number;
  lat: number;
  lng: number;
  explanation: string;
}

interface ParcelsListProps {
  parcels: Parcel[];
  onParcelClick: (parcel: Parcel) => void;
}

const ParcelsList = ({ parcels, onParcelClick }: ParcelsListProps) => {
  if (parcels.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">No parcels to display. Try searching for parcels using the chat.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4 h-full overflow-y-auto">
      <div className="sticky top-0 bg-background pb-2 z-10">
        <h2 className="text-lg font-semibold">Top Eligible Parcels ({parcels.length})</h2>
        <p className="text-sm text-muted-foreground">Click on a parcel to view on map</p>
      </div>
      
      {parcels.map((parcel, index) => (
        <Card
          key={index}
          className="cursor-pointer hover:shadow-medium transition-all hover:border-primary/50"
          onClick={() => onParcelClick(parcel)}
        >
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-2">
              <CardTitle className="text-base font-semibold leading-tight">
                {parcel.address}
              </CardTitle>
              <Badge variant="secondary" className="bg-primary/10 text-primary flex-shrink-0">
                #{index + 1}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <MapPin className="w-4 h-4 text-primary" />
                <span>{parcel.county} County</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Ruler className="w-4 h-4 text-primary" />
                <span>{parcel.acreage} acres</span>
              </div>
            </div>
            
            <div className="bg-accent/50 rounded-lg p-3 border border-border">
              <p className="text-sm text-foreground leading-relaxed">
                {parcel.explanation}
              </p>
            </div>
            
            <div className="text-xs text-muted-foreground">
              Coordinates: {parcel.lat.toFixed(4)}, {parcel.lng.toFixed(4)}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default ParcelsList;
