# Deploy Frontend to Vercel

## Step 1: Configure Vercel Project Settings

1. Go to [vercel.com](https://vercel.com) and sign in
2. Go to your project (or create a new one)
3. Go to **Settings** → **General**
4. Set **Root Directory** to: `frontend`
5. Save changes

## Step 2: Add Environment Variable

1. Go to **Settings** → **Environment Variables**
2. Add a new variable:
   - **Name**: `VITE_API_URL`
   - **Value**: Your Railway backend URL (e.g., `https://your-app.railway.app`)
   - **Environment**: Select all (Production, Preview, Development)
3. Click **Save**

## Step 3: Deploy

### Option A: Automatic Deployment (Recommended)
- Push to your GitHub repository
- Vercel will automatically deploy

### Option B: Manual Deployment
1. Go to **Deployments** tab
2. Click **Redeploy** on the latest deployment
3. Or use CLI: `vercel --prod`

## Step 4: Verify Deployment

1. Visit your Vercel URL (e.g., `https://your-app.vercel.app`)
2. The frontend should load
3. Test the API connection by making a search query

## Step 5: Update Backend CORS (if needed)

If you get CORS errors, update the `ALLOWED_ORIGINS` environment variable in Railway:

1. Go to Railway Dashboard → Your Service → Variables
2. Update `ALLOWED_ORIGINS` to include your Vercel domain:
   ```
   https://your-app.vercel.app,https://your-app-git-main.vercel.app
   ```
3. Redeploy the backend

## Troubleshooting

- **CORS errors**: Make sure `ALLOWED_ORIGINS` in Railway includes your Vercel domain
- **API not found**: Verify `VITE_API_URL` is set correctly in Vercel
- **Build fails**: Check Vercel build logs for errors

