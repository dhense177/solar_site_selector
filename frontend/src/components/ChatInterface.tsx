import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Send, Loader2, Sparkles, RotateCcw } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface Message {
  role: "user" | "assistant";
  content: string;
}

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

interface ChatInterfaceProps {
  onParcelsFound: (parcels: Parcel[]) => void;
}

const SUGGESTED_PROMPTS = [
  "Find parcels over 20 acres in Franklin county away from wetlands",
  "Show flat land parcels over 15 acres in Worcester county",
  "Find parcels with southern exposure in Berkshire county",
  "Search for 25+ acre parcels near grid infrastructure in Hampshire county"
];

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ChatInterface = ({ onParcelsFound }: ChatInterfaceProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const { toast } = useToast();

  const handleSubmit = async (queryText?: string) => {
    const query = queryText || input;
    if (!query.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: query };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      console.log(`Sending request to ${API_BASE_URL}/api/search`);
      console.log('Query:', query);
      
      const response = await fetch(`${API_BASE_URL}/api/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
          query,
          session_id: sessionId || undefined
        }),
      });

      console.log('Response status:', response.status);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        const errorMessage = errorData.detail || `HTTP error! status: ${response.status}`;
        console.error('API error:', errorMessage);
        throw new Error(errorMessage);
      }

      const data = await response.json();

      console.log('Response from API:', data);

      // Store session ID for conversation continuity
      if (data.session_id) {
        setSessionId(data.session_id);
        console.log('Stored session_id:', data.session_id);
      }

      // Indicate if this was a refinement
      const refinementNote = data.is_refinement ? "\n\n(Refining previous search...)" : "";

      // Check if there's an error (topic filter failure or other error)
      if (data.summary && data.summary.startsWith("Error: ")) {
        const errorMessage = data.summary.replace("Error: ", "");
        const assistantMessage: Message = {
          role: "assistant",
          content: errorMessage
        };
        setMessages(prev => [...prev, assistantMessage]);
        onParcelsFound([]); // Clear parcels on error
        return;
      }

      if (data.parcels && data.parcels.length > 0) {
        console.log('ChatInterface: Received parcels from API:', {
          count: data.parcels.length,
          firstParcel: data.parcels[0] ? {
            address: data.parcels[0].address,
            hasGeometry: !!data.parcels[0].geometry,
            geometryType: data.parcels[0].geometry?.type,
            hasCoordinates: !!data.parcels[0].geometry?.coordinates
          } : null
        });
        onParcelsFound(data.parcels);
        const assistantMessage: Message = {
          role: "assistant",
          content: (data.summary || `Found ${data.parcels.length} parcels matching your criteria.`) + refinementNote
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        const assistantMessage: Message = {
          role: "assistant",
          content: (data.summary || "No parcels found matching your criteria. Try adjusting your search parameters.") + refinementNote
        };
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Error searching parcels:', error);
      
      let errorMessage = "Failed to search for parcels. Please try again.";
      
      if (error instanceof TypeError && error.message.includes('fetch')) {
        errorMessage = `Cannot connect to backend API at ${API_BASE_URL}. Make sure the backend server is running.`;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      
      const assistantErrorMessage: Message = {
        role: "assistant",
        content: `I encountered an error: ${errorMessage}`
      };
      setMessages(prev => [...prev, assistantErrorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestedPrompt = (prompt: string) => {
    // Clear session for new searches from suggested prompts
    setSessionId(null);
    setInput(prompt);
    handleSubmit(prompt);
  };

  const handleNewSearch = () => {
    // Clear session and messages to start fresh
    setSessionId(null);
    setMessages([]);
    setInput("");
    // Clear parcels on the map
    onParcelsFound([]);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header with Redo Search button */}
      {messages.length > 0 && (
        <div className="p-3 border-b bg-background/50">
          <Button
            variant="outline"
            size="sm"
            onClick={handleNewSearch}
            className="w-full gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Redo Search
          </Button>
        </div>
      )}
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {messages.length === 0 ? (
          <div className="space-y-4">
            <div className="text-center py-8">
              <Sparkles className="w-12 h-12 text-primary mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Ask About Solar Parcels</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Use the suggested prompts below or ask your own question
              </p>
            </div>
            <div className="grid gap-2">
              {SUGGESTED_PROMPTS.map((prompt, index) => (
                <Button
                  key={index}
                  variant="outline"
                  className="text-left h-auto py-3 px-4 whitespace-normal justify-start hover:bg-accent"
                  onClick={() => handleSuggestedPrompt(prompt)}
                >
                  <span className="text-sm">{prompt}</span>
                </Button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <Card
              key={index}
              className={`p-4 ${
                message.role === "user"
                  ? "bg-primary/10 ml-8"
                  : "bg-muted/50 mr-8"
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            </Card>
          ))
        )}
        {isLoading && (
          <Card className="p-4 bg-muted/50 mr-8">
            <div className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <p className="text-sm text-muted-foreground">Analyzing parcels...</p>
            </div>
          </Card>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-background">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Ask about parcels (e.g., 'Find 20+ acre parcels in Franklin county...')"
            className="min-h-[60px] resize-none"
            disabled={isLoading}
          />
          <Button
            onClick={() => handleSubmit()}
            disabled={isLoading || !input.trim()}
            size="icon"
            className="h-[60px] w-[60px] bg-gradient-primary hover:opacity-90"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
