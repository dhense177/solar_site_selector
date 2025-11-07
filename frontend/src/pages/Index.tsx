import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import OnboardingModal from "@/components/OnboardingModal";
import ChatInterface from "@/components/ChatInterface";
import MapView from "@/components/MapView";
import { HelpCircle } from "lucide-react";

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

const Index = () => {
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [selectedParcel, setSelectedParcel] = useState<Parcel | null>(null);

  useEffect(() => {
    const hasSeenOnboarding = localStorage.getItem("hasSeenOnboarding");
    if (hasSeenOnboarding) {
      setShowOnboarding(false);
    }
  }, []);

  const handleCloseOnboarding = () => {
    localStorage.setItem("hasSeenOnboarding", "true");
    setShowOnboarding(false);
  };

  const handleParcelsFound = (newParcels: Parcel[]) => {
    console.log('Index: Received parcels:', {
      count: newParcels.length,
      firstParcel: newParcels[0] ? {
        address: newParcels[0].address,
        hasGeometry: !!newParcels[0].geometry,
        geometryType: newParcels[0].geometry?.type,
        hasCoordinates: !!newParcels[0].geometry?.coordinates
      } : null
    });
    setParcels(newParcels);
    setSelectedParcel(null);
  };

  return (
    <div className="h-screen flex flex-col bg-gradient-soft">
      {/* Header */}
      <header className="bg-background border-b border-border shadow-soft">
        <div className="container mx-auto px-4 py-2 relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center h-16">
              <img 
                src="/yuma.png" 
                alt="Logo" 
                className="h-full w-auto object-contain"
              />
            </div>
            <h1 className="text-2xl font-bold absolute left-1/2 transform -translate-x-1/2" style={{ color: '#FFB300', fontFamily: 'Futura Md BT, sans-serif' }}>
              Massachusetts Utility-Scale Solar Site Selection Assistant
            </h1>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowOnboarding(true)}
              className="gap-2"
            >
              <HelpCircle className="w-4 h-4" />
              Help
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto p-4 overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-4 h-full">
          {/* Left Column - Chat (narrower, fixed width) */}
          <Card className="flex flex-col overflow-hidden shadow-medium">
            <ChatInterface onParcelsFound={handleParcelsFound} />
          </Card>

          {/* Right Column - Map takes full height */}
          <Card className="overflow-hidden shadow-medium flex-1" style={{ minHeight: "500px", display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, width: "100%", position: "relative", minHeight: "500px" }}>
              <MapView parcels={parcels} selectedParcel={selectedParcel} />
            </div>
          </Card>
        </div>
      </main>

      {/* Onboarding Modal */}
      <OnboardingModal isOpen={showOnboarding} onClose={handleCloseOnboarding} />
    </div>
  );
};

export default Index;
