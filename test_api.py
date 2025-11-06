#!/usr/bin/env python3
"""Test script to call the API endpoint and show debug output"""
import requests
import json

# Make a test request
response = requests.post(
    "http://localhost:8000/api/search",
    json={"query": "Find me all sites in Franklin county that are more than 20 acres"}
)

print("=" * 80)
print("API RESPONSE:")
print("=" * 80)
print(f"Status Code: {response.status_code}")
print(f"\nResponse JSON:")
print(json.dumps(response.json(), indent=2))
print("=" * 80)

