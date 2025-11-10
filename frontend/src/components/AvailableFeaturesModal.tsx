import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface AvailableFeaturesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AvailableFeaturesModal = ({ isOpen, onClose }: AvailableFeaturesModalProps) => {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-3xl font-bold" style={{ color: '#FFB300' }}>
            Available Features
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Parcel Details */}
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">Parcel Details</h3>
            <ul className="space-y-1 text-sm text-muted-foreground ml-4">
              <li className="list-disc">Size</li>
              <li className="list-disc">Location (i.e. town, county)</li>
              <li className="list-disc">Total Land Value</li>
              <li className="list-disc">Capacity</li>
            </ul>
          </div>

          {/* Geographic Features */}
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">Geographic Features</h3>
            <ul className="space-y-1 text-sm text-muted-foreground ml-4">
              <li className="list-disc">Land Cover (i.e. wetlands, forests, etc...)</li>
              <li className="list-disc">Land Use (i.e. industrial, commercial, residential, etc...)</li>
              <li className="list-disc">Flood Zones</li>
              <li className="list-disc">Open Spaces (i.e. conservation lands, outdoor recreational facilities, etc...)</li>
              <li className="list-disc">Priority Habitats (rare and endangered species habitats)</li>
              <li className="list-disc">Prime Farmland Soils</li>
            </ul>
          </div>

          {/* Infrastructure */}
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">Infrastructure</h3>
            <ul className="space-y-1 text-sm text-muted-foreground ml-4">
              <li className="list-disc">Grid infrastructure (i.e. substations, power lines)</li>
              <li className="list-disc">Transportation infrastructure (i.e. highways, roads, etc...)</li>
            </ul>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#258222] text-white rounded-md hover:opacity-90"
          >
            Close
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AvailableFeaturesModal;

