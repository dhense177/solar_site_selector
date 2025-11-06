#!/bin/bash
# Test script to verify backend connectivity

echo "Testing backend connectivity..."
echo ""

# Test health endpoint
echo "1. Testing /api/health endpoint:"
curl -s http://localhost:8000/api/health
echo ""
echo ""

# Test root endpoint
echo "2. Testing root endpoint:"
curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/
echo ""
echo ""

# Test CORS preflight
echo "3. Testing CORS preflight (OPTIONS request):"
curl -X OPTIONS http://localhost:8000/api/search \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v 2>&1 | grep -E "(< HTTP|< Access-Control)" | head -5
echo ""
echo ""

# Test actual POST request
echo "4. Testing POST request with CORS headers:"
curl -X POST http://localhost:8000/api/search \
  -H "Origin: http://localhost:5173" \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' \
  -s | python3 -m json.tool 2>/dev/null | head -20 || echo "Request failed"
echo ""

echo "Done! If all tests pass, the backend is working correctly."

