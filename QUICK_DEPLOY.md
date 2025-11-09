# Quick Deploy to Vercel

## Step 1: Deploy Frontend to Vercel

### Option A: Using Vercel CLI (Recommended)

```bash
# Install Vercel CLI if you haven't
npm install -g vercel

# Login to Vercel
vercel login

# Deploy from project root
cd /Users/davidhenslovitz/Projects/solar_deep_research
vercel

# Follow prompts:
# - Set up and deploy? Yes
# - Which scope? (Select your account)
# - Link to existing project? No
# - Project name? solar-deep-research (or your choice)
# - Directory? frontend
# - Override settings? No
```

### Option B: Using Vercel Dashboard

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "Add New..." → "Project"
3. Import your Git repository
4. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite (auto-detected)
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `dist` (auto-detected)
5. Add Environment Variable:
   - **Name**: `VITE_API_URL`
   - **Value**: `https://your-backend-url.com` (you'll get this from Step 2)
6. Click "Deploy"

## Step 2: Deploy Backend (Choose One)

### Option A: Railway (Easiest)

1. Go to [railway.app](https://railway.app) and sign in
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add a new service → "Empty Service"
5. In the service settings:
   - **Root Directory**: `/` (project root)
   - **Build Command**: `uv sync` or `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api_server:api_app --host 0.0.0.0 --port $PORT`
6. Add Environment Variables:
   - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT`
   - `OPENAI_API_KEY`
   - `ALLOWED_ORIGINS`: `https://your-vercel-app.vercel.app` (from Step 1)
7. Railway will give you a URL like `https://your-app.railway.app`
8. Update `VITE_API_URL` in Vercel to this URL

### Option B: Render

1. Go to [render.com](https://render.com) and sign in
2. Click "New +" → "Web Service"
3. Connect your repository
4. Configure:
   - **Name**: `solar-deep-research-api`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api_server:api_app --host 0.0.0.0 --port $PORT`
5. Add environment variables (same as Railway)
6. Deploy

## Step 3: Update Environment Variables

### In Vercel (Frontend):
- `VITE_API_URL` = Your backend URL (from Step 2)

### In Backend Platform (Railway/Render):
- `ALLOWED_ORIGINS` = Your Vercel frontend URL (from Step 1)
- Database credentials
- `OPENAI_API_KEY`

## Step 4: Test

1. Visit your Vercel URL: `https://your-app.vercel.app`
2. Test the application
3. Check browser console for any errors

## Troubleshooting

- **CORS errors**: Make sure `ALLOWED_ORIGINS` includes your Vercel domain
- **API not found**: Verify `VITE_API_URL` is set correctly
- **Database errors**: Check database credentials and network access

