#!/bin/bash

# Deployment script for Solar Deep Research
# This script helps deploy the frontend to Vercel

set -e

echo "🚀 Solar Deep Research Deployment Script"
echo "========================================"
echo ""

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Installing..."
    npm install -g vercel
fi

# Check if logged in
if ! vercel whoami &> /dev/null; then
    echo "⚠️  Not logged in to Vercel. Please login first:"
    echo "   Run: vercel login"
    echo ""
    read -p "Press Enter after you've logged in..."
fi

echo "✅ Vercel CLI ready"
echo ""

# Navigate to project root
cd "$(dirname "$0")"

echo "📦 Building frontend..."
cd frontend
npm run build
cd ..

echo ""
echo "🌐 Deploying to Vercel..."
echo ""

# Deploy to Vercel
vercel --prod

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Get your Vercel deployment URL from the output above"
echo "   2. Deploy your backend (see QUICK_DEPLOY.md for options)"
echo "   3. Set VITE_API_URL in Vercel dashboard to your backend URL"
echo "   4. Set ALLOWED_ORIGINS in your backend to your Vercel URL"
echo ""

