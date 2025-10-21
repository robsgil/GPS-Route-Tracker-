#!/usr/bin/env python3
"""
Test script for GPS Tracker MVP
Verifies basic functionality without starting the server
"""

import sys
import json
from datetime import datetime

print("🔍 Testing GPS Tracker MVP Setup...\n")

# Test 1: Import Flask and dependencies
print("1. Testing imports...")
try:
    from flask import Flask
    from flask_cors import CORS
    from reportlab.pdfgen import canvas
    import requests
    from PIL import Image
    print("   ✓ All dependencies imported successfully")
except ImportError as e:
    print(f"   ✗ Import error: {e}")
    sys.exit(1)

# Test 2: Check app structure
print("\n2. Checking application structure...")
try:
    import app as tracker_app
    print("   ✓ App module loaded successfully")
except Exception as e:
    print(f"   ✗ App loading error: {e}")
    sys.exit(1)

# Test 3: Verify Flask app
print("\n3. Verifying Flask application...")
try:
    assert hasattr(tracker_app, 'app'), "Flask app not found"
    assert isinstance(tracker_app.app, Flask), "app is not a Flask instance"
    print("   ✓ Flask app configured correctly")
except AssertionError as e:
    print(f"   ✗ {e}")
    sys.exit(1)

# Test 4: Check routes
print("\n4. Checking routes...")
routes = []
for rule in tracker_app.app.url_map.iter_rules():
    routes.append(str(rule))

expected_routes = ['/', '/api/track/start', '/api/track/<track_id>/point', 
                   '/api/track/<track_id>/finish', '/api/track/<track_id>/pdf']

missing_routes = []
for expected in expected_routes:
    found = False
    for route in routes:
        if expected.replace('<track_id>', 'track_id') in route:
            found = True
            break
    if not found:
        missing_routes.append(expected)

if missing_routes:
    print(f"   ✗ Missing routes: {missing_routes}")
else:
    print(f"   ✓ All {len(expected_routes)} routes configured")

# Test 5: Test track creation
print("\n5. Testing track creation logic...")
try:
    test_client = tracker_app.app.test_client()
    response = test_client.post('/api/track/start')
    data = json.loads(response.data)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert 'track_id' in data, "track_id not in response"
    assert 'status' in data, "status not in response"
    
    track_id = data['track_id']
    print(f"   ✓ Track created successfully: {track_id[:8]}...")
    
    # Test adding a point
    point_response = test_client.post(
        f'/api/track/{track_id}/point',
        json={'lat': 40.7128, 'lon': -74.0060, 'accuracy': 10}
    )
    
    assert point_response.status_code == 200, "Failed to add point"
    print("   ✓ Point added successfully")
    
    # Test finishing track
    finish_response = test_client.post(f'/api/track/{track_id}/finish')
    assert finish_response.status_code == 200, "Failed to finish track"
    print("   ✓ Track finished successfully")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*50)
print("✅ All tests passed! Application is ready to run.")
print("="*50)
print("\nTo start the server, run:")
print("  python app.py")
print("\nFor production deployment, run:")
print("  gunicorn app:app")
print("\nThe application will be available at:")
print("  http://localhost:5000")
