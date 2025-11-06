# solar_deep_research

Solar parcel finder integrating natural language SQL queries with a React frontend.

## Architecture

- **Backend**: FastAPI server (`api_server.py`) that wraps `sql_agent.py` (LangGraph-based SQL query agent)
- **Frontend**: React + TypeScript application (`frontend/`) with chat interface and map visualization
- **Database**: PostgreSQL with PostGIS extension

## Setup

### Backend Setup

1. Install Python dependencies:
```bash
uv sync  # or pip install -e .
```

2. Set up environment variables in `.env`:
```
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
OPENAI_API_KEY=your_openai_api_key
```

3. Start the API server:
```bash
python api_server.py
# or
./start_api.sh
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file (optional, defaults to `http://localhost:8000`):
```
VITE_API_URL=http://localhost:8000
```

4. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

1. Start the backend API server (`python api_server.py`)
2. Start the frontend development server (`cd frontend && npm run dev`)
3. Open `http://localhost:5173` in your browser
4. Use the chat interface to search for parcels using natural language queries

## API Endpoints

### POST `/api/search`

Search for parcels using natural language query.

**Request:**
```json
{
  "query": "Find parcels over 20 acres in Franklin county"
}
```

**Response:**
```json
{
  "parcels": [
    {
      "address": "123 Main St",
      "county": "FRANKLIN",
      "acreage": 25.5,
      "lat": 42.123,
      "lng": -72.456,
      "explanation": "Found parcel matching your criteria"
    }
  ],
  "summary": "Found 1 parcel matching your criteria.",
  "sql": "SELECT ...",
  "unimplemented_filters": null
}
```

### GET `/api/health`

Health check endpoint.

## Integration Details

The frontend (`ChatInterface.tsx`) communicates with the backend API (`api_server.py`) which:
1. Receives natural language queries
2. Uses `sql_agent.py` to generate and execute SQL queries
3. Transforms database results to match frontend format
4. Extracts lat/lng coordinates from PostGIS geometries
5. Returns formatted parcel data

The SQL agent automatically:
- Generates SQL queries from natural language
- Validates and repairs queries
- Handles errors and retries
- Checks for unimplemented filters
