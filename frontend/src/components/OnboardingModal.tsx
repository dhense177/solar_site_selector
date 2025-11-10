import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Lightbulb, MapPin, MessageSquare, Zap } from "lucide-react";

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const OnboardingModal = ({ isOpen, onClose }: OnboardingModalProps) => {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-3xl font-bold" style={{ color: '#FFB300' }}>
            Welcome to Yuma
          </DialogTitle>
          {/* Subtitle - appears right under the title */}
          <p className="text-md font-bold text-muted-foreground pt-1" style={{ color: '#000000' }}>The site selection tool for large-scale solar projects in Massachusetts</p>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-accent/50 border border-border">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-sm mb-1">Ask Questions</h3>
                <p className="text-xs text-muted-foreground">
                  Use the chat to search for parcels with specific criteria
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-lg bg-accent/50 border border-border">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <MapPin className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-sm mb-1">View On Map</h3>
                <p className="text-xs text-muted-foreground">
                  See eligible parcels displayed on the interactive map
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-lg bg-accent/50 border border-border">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Lightbulb className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-sm mb-1">Locate Suitable Parcels</h3>
                <p className="text-xs text-muted-foreground">
                  Get details about each recommended parcel, powered by AI
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-lg bg-accent/50 border border-border">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Zap className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-sm mb-1">Try Guided Prompts</h3>
                <p className="text-xs text-muted-foreground">
                  Use suggested questions to get started quickly
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3 p-4 rounded-lg bg-muted/50 border border-border">
            <h3 className="font-semibold text-sm">Example Questions:</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <span className="text-primary mt-0.5">•</span>
                <span>"Search for 25+ acre parcels within 1 km of substations in Pittsfield, MA"</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-0.5">•</span>
                <span>"Find parcels with at least 50 MW of ground-mount capacity in Worcester county"</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-0.5">•</span>
                <span>"Find me 20+ acre sites within industrial zones in Franklin County"</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button onClick={onClose} className="bg-gradient-primary hover:opacity-90">
            Get Started
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default OnboardingModal;
