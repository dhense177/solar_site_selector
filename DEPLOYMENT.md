# Deployment Guide for Solar Deep Research

This guide covers deploying both the frontend and backend of the application.

## Architecture

- **Frontend**: React + Vite application (deploy to Vercel)
- **Backend**: FastAPI application with PostgreSQL database (deploy separately)

## Option 1: Deploy Frontend to Vercel (Recommended)

### Prerequisites

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

### Deploy Frontend

1. Navigate to the project root:
```bash
cd /Users/davidhenslovitz/Projects/solar_deep_research
```

2. Deploy to Vercel:
```bash
vercel
```

3. Follow the prompts:
   - Set up and deploy? **Yes**
   - Which scope? (Select your account)
   - Link to existing project? **No**
   - Project name? (e.g., `solar-deep-research`)
   - Directory? **frontend**
   - Override settings? **No**

4. Set environment variables in Vercel dashboard:
   - Go to your project settings → Environment Variables
   - Add: `VITE_API_URL` = `https://your-backend-url.com` (see backend deployment below)

5. Redeploy after setting environment variables:
```bash
vercel --prod
```

### Alternative: Deploy via Vercel Dashboard

1. Go to [vercel.com](https://vercel.com)
2. Click "New Project"
3. Import your Git repository
4. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. Add environment variable: `VITE_API_URL` = your backend URL
6. Click "Deploy"

## Option 2: Deploy Backend

The backend (FastAPI) needs to be deployed separately. Recommended platforms:

### A. Railway (Recommended for Backend)

1. Go to [railway.app](https://railway.app)
2. Create a new project
3. Connect your GitHub repository
4. Add a new service → "Empty Service"
5. Configure:
   - **Build Command**: `pip install -r requirements.txt` (or use `uv`)
   - **Start Command**: `uvicorn api_server:api_app --host 0.0.0.0 --port $PORT`
   - **Root Directory**: `/` (project root)
6. Add environment variables:
   - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT`
   - `OPENAI_API_KEY`
   - `SUPABASE_URL_SESSION` (if using Supabase)
7. Railway will provide a URL like `https://your-app.railway.app`
8. Update `VITE_API_URL` in Vercel to point to this URL

### B. Render

1. Go to [render.com](https://render.com)
2. Create a new "Web Service"
3. Connect your repository
4. Configure:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api_server:api_app --host 0.0.0.0 --port $PORT`
5. Add environment variables (same as Railway)
6. Render will provide a URL

### C. Fly.io

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Initialize: `fly launch`
4. Deploy: `fly deploy`

## Option 3: Deploy Backend as Vercel Serverless Functions

If you want everything on Vercel, you can convert the FastAPI backend to serverless functions:

1. Create `api/` directory in project root
2. Convert FastAPI routes to Vercel serverless functions
3. This is more complex and may have limitations with database connections

## Environment Variables

### Frontend (Vercel)
- `VITE_API_URL`: Backend API URL (e.g., `https://your-backend.railway.app`)

### Backend (Railway/Render/etc.)
- `DB_HOST`: Database host
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password
- `DB_NAME`: Database name
- `DB_PORT`: Database port (usually 5432)
- `OPENAI_API_KEY`: OpenAI API key
- `SUPABASE_URL_SESSION`: Supabase connection string (if applicable)

## CORS Configuration

After deploying the backend, update `api_server.py` to include your Vercel frontend URL in the CORS allowed origins:

```python
allow_origins=[
    "https://your-app.vercel.app",
    "https://your-app.vercel.app/*",
    # ... other origins
]
```

## Testing Deployment

1. Frontend should be accessible at `https://your-app.vercel.app`
2. Backend API should be accessible at `https://your-backend.railway.app/api/health`
3. Test the full flow: frontend → backend → database

## Troubleshooting

- **CORS errors**: Make sure backend CORS includes your Vercel domain
- **API connection errors**: Verify `VITE_API_URL` is set correctly in Vercel
- **Database connection errors**: Check database credentials and network access
- **Build errors**: Check build logs in Vercel dashboard

