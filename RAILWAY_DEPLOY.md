# Deploy Backend to Railway

## Step 1: Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up or log in (you can use GitHub to sign in)

## Step 2: Create New Project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose your repository: `dhense177/solar_deep_research`
4. Railway will create a new project

## Step 3: Configure the Service

1. Railway will automatically detect Python and create a service
2. If it doesn't, click "New" → "Empty Service"
3. Click on the service to configure it

## Step 4: Set Build and Start Commands

In the service settings:

**Build Command:**
```
pip install -r requirements.txt
```

**Start Command:**
```
cd backend && uvicorn api_server:api_app --host 0.0.0.0 --port $PORT
```

**Root Directory:**
```
/ (project root)
```

**Note:** The backend code is now in the `backend/` directory. Railway will use the `Procfile` or `railway.json` which already includes the `cd backend` command.

## Step 5: Add Environment Variables

Go to the service → Variables tab and add:

### Database Connection:
- `DB_HOST` - Your database host (e.g., `your-db.railway.app` or `localhost`)
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_NAME` - Database name
- `DB_PORT` - Database port (usually `5432`)

### API Keys:
- `OPENAI_API_KEY` - Your OpenAI API key

### CORS:
- `ALLOWED_ORIGINS` - Comma-separated list of allowed origins (e.g., `https://your-vercel-app.vercel.app,https://your-vercel-app-git-main.vercel.app`)

### Optional (if using Supabase):
- `SUPABASE_URL_SESSION` - Supabase connection string
- `SUPABASE_PWD` - Supabase password

## Step 6: Deploy

1. Railway will automatically deploy when you push to GitHub
2. Or click "Deploy" in the Railway dashboard
3. Wait for the deployment to complete

## Step 7: Get Your Backend URL

1. After deployment, Railway will provide a URL like: `https://your-app.railway.app`
2. Copy this URL

## Step 8: Update Frontend Environment Variable

1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables
2. Add or update: `VITE_API_URL` = `https://your-app.railway.app` (from Step 7)
3. Redeploy the frontend on Vercel

## Step 9: Test

1. Visit your Vercel frontend URL
2. Test the API: `https://your-app.railway.app/api/health`
3. Should return: `{"status": "ok", ...}`

## Troubleshooting

- **Build fails**: Check that `requirements.txt` has all dependencies
- **App crashes**: Check Railway logs for errors
- **Database connection fails**: Verify database credentials and network access
- **CORS errors**: Make sure `ALLOWED_ORIGINS` includes your Vercel domain

