import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { query } = await req.json();
    console.log('Received query:', query);

    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

    // System prompt that understands Massachusetts solar parcel requirements
    const systemPrompt = `You are a solar parcel analysis expert for Massachusetts. 

Your role is to analyze land parcels for solar energy development potential. You should:
1. Parse user queries about land criteria (acreage, location, environmental constraints)
2. Generate realistic parcel recommendations based on Massachusetts geography
3. Explain why each parcel is suitable for solar development
4. Consider factors like: size, location, proximity to wetlands, soil type, slope, grid access

For each recommendation, provide:
- Address (realistic MA address format)
- County
- Acreage
- Lat/Lng coordinates (within Massachusetts bounds: 41.2-42.9 lat, -73.5 to -69.9 lng)
- Brief explanation of solar suitability

Response format must be valid JSON:
{
  "parcels": [
    {
      "address": "123 Main St, Town, MA 01234",
      "county": "County Name",
      "acreage": 25.5,
      "lat": 42.3601,
      "lng": -71.0589,
      "explanation": "Ideal for solar: flat terrain, 25+ acres, away from wetlands, southern exposure"
    }
  ],
  "summary": "Found X parcels matching your criteria..."
}

Massachusetts counties: Barnstable, Berkshire, Bristol, Dukes, Essex, Franklin, Hampden, Hampshire, Middlesex, Nantucket, Norfolk, Plymouth, Suffolk, Worcester

Be realistic and specific. Consider actual MA geography.`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: query }
        ],
        temperature: 0.7,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);
      
      if (response.status === 429) {
        return new Response(
          JSON.stringify({ error: "Rate limit exceeded. Please try again later." }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      
      if (response.status === 402) {
        return new Response(
          JSON.stringify({ error: "Payment required. Please add credits to continue." }),
          { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      throw new Error(`AI gateway error: ${response.status}`);
    }

    const data = await response.json();
    const content = data.choices[0].message.content;
    console.log('AI response:', content);

    // Try to parse JSON response
    let parsedData;
    try {
      parsedData = JSON.parse(content);
    } catch (e) {
      console.error('Failed to parse AI response as JSON:', content);
      // Return a structured error response
      parsedData = {
        parcels: [],
        summary: "Unable to process the query. Please try rephrasing your question.",
        error: "Invalid response format"
      };
    }

    return new Response(JSON.stringify(parsedData), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Error in solar-parcel-search:", error);
    return new Response(
      JSON.stringify({ 
        error: error instanceof Error ? error.message : "Unknown error",
        parcels: [],
        summary: "An error occurred while processing your request."
      }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
