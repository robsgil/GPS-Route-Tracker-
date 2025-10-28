from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from datetime import datetime
import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image
import uuid
import os
import requests

app = Flask(__name__)
CORS(app)

# Store tracks in memory
tracks = {}

# OpenRouteService API Configuration
secretKeyForOpenRoute = os.getenv("OPENROUTE_SERVICE_KEY)
OPENROUTE_API_KEY = secretKeyForOpenRoute 
OPENROUTE_API_URL = "https://api.openrouteservice.org/v2/directions/foot-walking"

# Enhanced HTML with OpenRouteService route filling
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPS Route Tracker</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            border-bottom: 3px solid #667eea;
        }
        
        .header-content {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .logo {
            font-size: 40px;
            animation: bounce 2s infinite;
        }
        
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        
        .header-text h1 {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        
        .header-text p {
            font-size: 14px;
            color: #666;
            font-weight: 500;
        }
        
        .controls {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 25px 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 14px 28px;
            font-size: 16px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            box-shadow: none;
        }
        
        .btn:active:not(:disabled) {
            transform: scale(0.95);
        }
        
        .btn-icon {
            font-size: 20px;
        }
        
        .btn-start {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        
        .btn-start:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(17, 153, 142, 0.4);
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            color: white;
        }
        
        .btn-stop:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(235, 51, 73, 0.4);
        }
        
        .btn-download {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-download:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(102, 126, 234, 0.4);
        }
        
        .status {
            flex: 1;
            display: flex;
            gap: 30px;
            font-size: 14px;
            min-width: 300px;
        }
        
        .status-item {
            display: flex;
            flex-direction: column;
            padding: 10px 15px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 10px;
            min-width: 100px;
        }
        
        .status-label {
            font-size: 11px;
            color: #888;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }
        
        .status-value {
            font-weight: 700;
            font-size: 20px;
            color: #333;
        }
        
        .status-value.active {
            color: #11998e;
        }
        
        .status-value.inactive {
            color: #eb3349;
        }
        
        #map {
            flex: 1;
            min-height: 400px;
            box-shadow: inset 0 4px 20px rgba(0, 0, 0, 0.1);
        }
        
        .alert {
            padding: 15px 30px;
            font-size: 14px;
            font-weight: 500;
            display: none;
            animation: slideDown 0.3s ease;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .alert-warning {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .alert-success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        
        .alert-error {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            color: white;
        }
        
        .tracking-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #eb3349;
            display: inline-block;
            margin-right: 8px;
            box-shadow: 0 0 10px rgba(235, 51, 73, 0.5);
        }
        
        .tracking-indicator.active {
            background: #11998e;
            animation: pulse 2s infinite;
            box-shadow: 0 0 20px rgba(17, 153, 142, 0.8);
        }
        
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.7;
                transform: scale(1.2);
            }
        }
        
        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .leaflet-popup-content-wrapper {
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }
        
        .leaflet-popup-content {
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            margin: 15px;
        }
        
        @media (max-width: 768px) {
            .header {
                padding: 15px 20px;
            }
            
            .header-text h1 {
                font-size: 22px;
            }
            
            .header-text p {
                font-size: 12px;
            }
            
            .controls {
                flex-direction: column;
                align-items: stretch;
                padding: 20px;
            }
            
            .status {
                flex-direction: column;
                gap: 10px;
                width: 100%;
            }
            
            .status-item {
                width: 100%;
            }
            
            .btn {
                width: 100%;
                justify-content: center;
                padding: 16px 28px;
            }
        }
        
        .toast {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: white;
            padding: 20px 25px;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
            display: none;
            z-index: 10000;
            animation: slideUp 0.3s ease;
            max-width: 400px;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .toast.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <div class="logo">🗺️</div>
                <div class="header-text">
                    <h1>GPS Route Tracker</h1>
                    <p>Track your journey with smart route filling</p>
                </div>
            </div>
        </div>
        
        <div class="alert alert-warning" id="alertBanner">
            <span id="alertMessage">📍 Please allow location access to begin tracking.</span>
        </div>
        
        <div class="controls">
            <button class="btn btn-start" id="startBtn" onclick="startTracking()">
                <span class="btn-icon">▶</span>
                <span id="startBtnText">Start Tracking</span>
            </button>
            <button class="btn btn-stop" id="stopBtn" onclick="stopTracking()" disabled>
                <span class="btn-icon">⏹</span>
                <span>Stop Tracking</span>
            </button>
            <button class="btn btn-download" id="downloadBtn" onclick="downloadPDF()" disabled>
                <span class="btn-icon">⬇</span>
                <span id="downloadBtnText">Download PDF</span>
            </button>
            
            <div class="status">
                <div class="status-item">
                    <span class="status-label">Status</span>
                    <span class="status-value inactive" id="statusText">
                        <span class="tracking-indicator" id="indicator"></span>
                        Inactive
                    </span>
                </div>
                <div class="status-item">
                    <span class="status-label">Points</span>
                    <span class="status-value" id="pointCount">0</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Distance</span>
                    <span class="status-value" id="distance">0.00 km</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Duration</span>
                    <span class="status-value" id="duration">00:00</span>
                </div>
            </div>
        </div>
        
        <div id="map"></div>
    </div>
    
    <div class="toast" id="toast">
        <strong id="toastTitle">Notification</strong>
        <p id="toastMessage"></p>
    </div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script>
        // Global variables
        let map, trackId = null, isTracking = false, watchId = null;
        let routePolyline = null, currentMarker = null, routePoints = [], totalDistance = 0;
        let startMarker = null, trackingStartTime = null, durationInterval = null;
        let lastPointTime = null, lastPointData = null;
        
        // Gap detection threshold - 30 seconds or 200 meters triggers route filling
        const GAP_TIME_THRESHOLD = 30;
        const GAP_DISTANCE_THRESHOLD = 0.2;
        
        // Initialize map
        function initMap() {
            console.log('Initializing map...');
            map = L.map('map').setView([20, 0], 2);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19
            }).addTo(map);
            
            // Try to get initial position
            if (navigator.geolocation) {
                console.log('Geolocation is supported');
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        console.log('Initial position:', lat, lon);
                        map.setView([lat, lon], 15);
                        
                        L.circleMarker([lat, lon], {
                            radius: 8,
                            fillColor: '#667eea',
                            color: '#fff',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.8
                        }).addTo(map).bindPopup('Your current location');
                        
                        showToast('Location Found', 'Ready to start tracking!');
                    },
                    (error) => {
                        console.log('Initial position error:', error);
                        showAlert('Unable to get your location. Make sure location services are enabled.', 'warning');
                    }
                );
            } else {
                showAlert('Geolocation is not supported by your browser', 'error');
            }
        }
        
        // Calculate distance between two points (Haversine formula)
        function calculateDistance(lat1, lon1, lat2, lon2) {
            const R = 6371;
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                     Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                     Math.sin(dLon/2) * Math.sin(dLon/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }
        
        // Update duration display
        function updateDuration() {
            if (!trackingStartTime) return;
            
            const now = Date.now();
            const elapsed = Math.floor((now - trackingStartTime) / 1000);
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            
            document.getElementById('duration').textContent = 
                String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
        }
        
        // Fit map to show entire route before capture
        function fitMapToRoute() {
            if (routePoints.length === 0) return;
            
            try {
                const bounds = L.latLngBounds(routePoints);
                map.fitBounds(bounds, { 
                    padding: [50, 50],
                    maxZoom: 16
                });
                console.log('Map fitted to route bounds');
            } catch (error) {
                console.error('Error fitting map:', error);
            }
        }
        
        // Capture map as image
        async function captureMapImage() {
            try {
                console.log('Fitting map to show full route...');
                fitMapToRoute();
                
                // Wait for tiles to load
                await new Promise(resolve => setTimeout(resolve, 1500));
                
                console.log('Capturing map image...');
                const mapElement = document.getElementById('map');
                
                const canvas = await html2canvas(mapElement, {
                    useCORS: true,
                    allowTaint: true,
                    backgroundColor: '#f0f0f0',
                    scale: 2
                });
                
                const imageData = canvas.toDataURL('image/png');
                console.log('Map image captured successfully');
                
                return imageData;
            } catch (error) {
                console.error('Error capturing map:', error);
                return null;
            }
        }
        
        // Fill route gap using backend API
        async function fillRouteGap(fromLat, fromLon, toLat, toLon) {
            try {
                console.log(`Requesting route fill from [${fromLat}, ${fromLon}] to [${toLat}, ${toLon}]`);
                showToast('Filling Route Gap', 'Getting walking directions...');
                
                const response = await fetch('/api/route/fill', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start: [fromLon, fromLat],
                        end: [toLon, toLat]
                    })
                });
                
                if (!response.ok) {
                    console.error('Route fill failed');
                    return null;
                }
                
                const data = await response.json();
                
                if (data.route && data.route.length > 0) {
                    console.log(`Route filled with ${data.route.length} points`);
                    return data.route; // Returns array of [lat, lon]
                }
                
                return null;
            } catch (error) {
                console.error('Error filling route:', error);
                return null;
            }
        }
        
        // Start tracking
        async function startTracking() {
            if (!navigator.geolocation) {
                showAlert('Geolocation is not supported by your browser', 'error');
                return;
            }
            
            const startBtn = document.getElementById('startBtn');
            const startBtnText = document.getElementById('startBtnText');
            startBtn.disabled = true;
            startBtnText.innerHTML = '<span class="spinner"></span> Initializing...';
            
            showAlert('Requesting location permission...', 'warning');
            
            try {
                const permissionResult = await navigator.permissions.query({ name: 'geolocation' });
                
                if (permissionResult.state === 'denied') {
                    showAlert('Location permission denied. Please enable location access.', 'error');
                    startBtn.disabled = false;
                    startBtnText.textContent = 'Start Tracking';
                    return;
                }
                
                const response = await fetch('/api/track/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error('Failed to start tracking');
                }
                
                const data = await response.json();
                trackId = data.track_id;
                console.log('Track started with ID:', trackId);
                
                // Reset state
                routePoints = [];
                totalDistance = 0;
                trackingStartTime = Date.now();
                lastPointTime = null;
                lastPointData = null;
                
                // Clear existing markers and polylines
                if (routePolyline) map.removeLayer(routePolyline);
                if (startMarker) map.removeLayer(startMarker);
                if (currentMarker) map.removeLayer(currentMarker);
                
                // Start watching position
                watchId = navigator.geolocation.watchPosition(
                    handlePosition,
                    handleError,
                    {
                        enableHighAccuracy: true,
                        maximumAge: 1000,
                        timeout: 10000
                    }
                );
                
                isTracking = true;
                updateUI();
                
                // Start duration timer
                durationInterval = setInterval(updateDuration, 1000);
                
                hideAlert();
                showToast('Tracking Started', 'Your route is being recorded!');
                
            } catch (error) {
                console.error('Error starting track:', error);
                showAlert('Failed to start tracking. Please try again.', 'error');
                startBtn.disabled = false;
                startBtnText.textContent = 'Start Tracking';
            }
        }
        
        // Handle position update with automatic route filling
        async function handlePosition(position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            const currentTime = Date.now();
            
            console.log(`Position update: ${lat}, ${lon} (accuracy: ${accuracy}m)`);
            
            try {
                // Check for gap if we have previous point
                let shouldFillGap = false;
                if (lastPointTime && lastPointData) {
                    const timeDiff = (currentTime - lastPointTime) / 1000;
                    const distance = calculateDistance(
                        lastPointData[0], lastPointData[1],
                        lat, lon
                    );
                    
                    // Detect gap
                    if (timeDiff > GAP_TIME_THRESHOLD || distance > GAP_DISTANCE_THRESHOLD) {
                        console.log(`GAP DETECTED: ${timeDiff.toFixed(0)}s, ${(distance*1000).toFixed(0)}m`);
                        shouldFillGap = true;
                    }
                }
                
                // If gap detected, fill with walking route
                if (shouldFillGap && lastPointData) {
                    const filledRoute = await fillRouteGap(
                        lastPointData[0], lastPointData[1],
                        lat, lon
                    );
                    
                    if (filledRoute && filledRoute.length > 0) {
                        // Add filled route points
                        for (let point of filledRoute) {
                            routePoints.push(point);
                            
                            // Send to backend
                            await fetch(`/api/track/${trackId}/point`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    lat: point[0],
                                    lon: point[1],
                                    timestamp: new Date().toISOString(),
                                    filled: true
                                })
                            });
                        }
                        
                        showToast('Route Filled', 'Added realistic walking path');
                    }
                }
                
                // Send current point to backend
                await fetch(`/api/track/${trackId}/point`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        lat: lat,
                        lon: lon,
                        accuracy: accuracy,
                        timestamp: new Date().toISOString(),
                        filled: false
                    })
                });
                
                const newPoint = [lat, lon];
                
                // Add start marker on first point
                if (routePoints.length === 0) {
                    startMarker = L.marker([lat, lon], {
                        icon: L.divIcon({
                            className: 'start-marker',
                            html: '<div style="background: #11998e; color: white; padding: 8px 12px; border-radius: 20px; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">START</div>',
                            iconSize: [60, 30]
                        })
                    }).addTo(map);
                    
                    map.setView([lat, lon], 16);
                }
                
                // Calculate distance
                if (routePoints.length > 0) {
                    const lastPoint = routePoints[routePoints.length - 1];
                    const distance = calculateDistance(lastPoint[0], lastPoint[1], lat, lon);
                    if (distance > 0.005) {
                        totalDistance += distance;
                    }
                }
                
                routePoints.push(newPoint);
                
                // Update polyline
                if (routePolyline) {
                    map.removeLayer(routePolyline);
                }
                
                routePolyline = L.polyline(routePoints, {
                    color: '#667eea',
                    weight: 5,
                    opacity: 0.8,
                    smoothFactor: 1
                }).addTo(map);
                
                // Update current position marker
                if (currentMarker) {
                    map.removeLayer(currentMarker);
                }
                
                currentMarker = L.circleMarker([lat, lon], {
                    radius: 10,
                    fillColor: '#11998e',
                    color: '#fff',
                    weight: 3,
                    opacity: 1,
                    fillOpacity: 1
                }).addTo(map);
                
                // Add accuracy circle
                L.circle([lat, lon], {
                    radius: accuracy,
                    fillColor: '#11998e',
                    fillOpacity: 0.1,
                    color: '#11998e',
                    weight: 1,
                    opacity: 0.3
                }).addTo(map);
                
                // Center map on current position
                map.panTo([lat, lon], {
                    animate: true,
                    duration: 0.5
                });
                
                // Update UI
                document.getElementById('pointCount').textContent = routePoints.length;
                document.getElementById('distance').textContent = totalDistance.toFixed(2) + ' km';
                
                // Update last point data
                lastPointTime = currentTime;
                lastPointData = newPoint;
                
            } catch (error) {
                console.error('Error adding point:', error);
            }
        }
        
        // Handle geolocation error
        function handleError(error) {
            console.error('Geolocation error:', error);
            
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    showAlert('Location permission denied.', 'error');
                    stopTracking();
                    break;
                case error.POSITION_UNAVAILABLE:
                    console.log('Position unavailable');
                    break;
                case error.TIMEOUT:
                    console.log('Position timeout');
                    break;
            }
        }
        
        // Stop tracking
        async function stopTracking() {
            console.log('Stopping tracking...');
            
            if (watchId) {
                navigator.geolocation.clearWatch(watchId);
                watchId = null;
            }
            
            if (durationInterval) {
                clearInterval(durationInterval);
                durationInterval = null;
            }
            
            if (trackId) {
                try {
                    showToast('Saving Route', 'Capturing map image...');
                    const mapImage = await captureMapImage();
                    
                    await fetch(`/api/track/${trackId}/finish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            total_distance: totalDistance,
                            map_image: mapImage
                        })
                    });
                    
                    showToast('Tracking Stopped', `Total distance: ${totalDistance.toFixed(2)} km`);
                    
                } catch (error) {
                    console.error('Error finishing track:', error);
                }
            }
            
            isTracking = false;
            updateUI();
        }
        
        // Download PDF
        async function downloadPDF() {
            if (!trackId) {
                showAlert('No track available to download', 'error');
                return;
            }
            
            const downloadBtn = document.getElementById('downloadBtn');
            const originalText = downloadBtn.innerHTML;
            downloadBtn.innerHTML = '<span class="btn-icon">⬇</span><span class="spinner"></span> Generating PDF...';
            downloadBtn.disabled = true;
            
            try {
                window.location.href = `/api/track/${trackId}/pdf`;
                showToast('Success', 'PDF download started!');
                
                setTimeout(() => {
                    downloadBtn.innerHTML = originalText;
                    downloadBtn.disabled = false;
                }, 2000);
                
            } catch (error) {
                console.error('Error downloading PDF:', error);
                showAlert('Failed to download PDF. Please try again.', 'error');
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
            }
        }
        
        // Update UI state
        function updateUI() {
            const startBtn = document.getElementById('startBtn');
            const startBtnText = document.getElementById('startBtnText');
            const stopBtn = document.getElementById('stopBtn');
            const downloadBtn = document.getElementById('downloadBtn');
            const statusText = document.getElementById('statusText');
            
            if (isTracking) {
                startBtn.disabled = true;
                stopBtn.disabled = false;
                downloadBtn.disabled = true;
                startBtnText.textContent = 'Tracking...';
                statusText.innerHTML = '<span class="tracking-indicator active"></span>Tracking';
                statusText.className = 'status-value active';
            } else {
                startBtn.disabled = false;
                startBtnText.textContent = 'Start Tracking';
                stopBtn.disabled = true;
                downloadBtn.disabled = trackId === null;
                statusText.innerHTML = '<span class="tracking-indicator"></span>' + (trackId ? 'Stopped' : 'Inactive');
                statusText.className = 'status-value ' + (trackId ? 'active' : 'inactive');
            }
        }
        
        // Show alert banner
        function showAlert(message, type = 'warning') {
            const banner = document.getElementById('alertBanner');
            const messageEl = document.getElementById('alertMessage');
            
            banner.className = 'alert alert-' + type;
            messageEl.textContent = message;
            banner.style.display = 'block';
        }
        
        // Hide alert banner
        function hideAlert() {
            document.getElementById('alertBanner').style.display = 'none';
        }
        
        // Show toast notification
        function showToast(title, message) {
            const toast = document.getElementById('toast');
            const toastTitle = document.getElementById('toastTitle');
            const toastMessage = document.getElementById('toastMessage');
            
            toastTitle.textContent = title;
            toastMessage.textContent = message;
            toast.className = 'toast show';
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 4000);
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            console.log('GPS Tracker initialized with route filling');
            initMap();
            updateUI();
        });
    </script>
</body>
</html>'''

@app.route('/')
def index():
    """Serve the main application page"""
    return Response(HTML_CONTENT, mimetype='text/html')

@app.route('/api/track/start', methods=['POST'])
def start_track():
    """Start a new tracking session"""
    track_id = str(uuid.uuid4())
    tracks[track_id] = {
        'id': track_id,
        'started_at': datetime.now().isoformat(),
        'points': [],
        'finished': False,
        'map_image': None
    }
    return jsonify({'track_id': track_id, 'status': 'started'})

@app.route('/api/track/<track_id>/point', methods=['POST'])
def add_point(track_id):
    """Add a GPS point to the track"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    data = request.json
    point = {
        'lat': data['lat'],
        'lon': data['lon'],
        'timestamp': data.get('timestamp', datetime.now().isoformat()),
        'accuracy': data.get('accuracy', None),
        'filled': data.get('filled', False)
    }
    
    tracks[track_id]['points'].append(point)
    return jsonify({'status': 'point_added', 'total_points': len(tracks[track_id]['points'])})

@app.route('/api/route/fill', methods=['POST'])
def fill_route():
    """Fill route gap using OpenRouteService API"""
    try:
        data = request.json
        start = data['start']  # [lon, lat]
        end = data['end']      # [lon, lat]
        
        # Check if API key is configured
        if OPENROUTE_API_KEY == "YOUR_API_KEY_HERE":
            print("Warning: OpenRouteService API key not configured. Returning straight line.")
            # Return simple straight line as fallback
            return jsonify({
                'route': [
                    [start[1], start[0]],
                    [end[1], end[0]]
                ],
                'distance': 0
            })
        
        # Call OpenRouteService API
        headers = {
            'Authorization': OPENROUTE_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'coordinates': [start, end],
            'preference': 'recommended',
            'units': 'km'
        }
        
        response = requests.post(
            OPENROUTE_API_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract route coordinates
            if 'routes' in result and len(result['routes']) > 0:
                geometry = result['routes'][0]['geometry']
                coordinates = geometry['coordinates']
                
                # Convert [lon, lat] to [lat, lon] for Leaflet
                route = [[coord[1], coord[0]] for coord in coordinates]
                distance = result['routes'][0]['summary']['distance']
                
                print(f"Route filled successfully: {len(route)} points, {distance} km")
                
                return jsonify({
                    'route': route,
                    'distance': distance
                })
        
        print(f"OpenRouteService API error: {response.status_code}")
        # Fallback to straight line
        return jsonify({
            'route': [
                [start[1], start[0]],
                [end[1], end[0]]
            ],
            'distance': 0
        })
        
    except Exception as e:
        print(f"Error filling route: {e}")
        # Return straight line as fallback
        return jsonify({
            'route': [
                [data['start'][1], data['start'][0]],
                [data['end'][1], data['end'][0]]
            ],
            'distance': 0
        })

@app.route('/api/track/<track_id>/finish', methods=['POST'])
def finish_track(track_id):
    """Finish tracking and save map image"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    data = request.json
    tracks[track_id]['finished'] = True
    tracks[track_id]['finished_at'] = datetime.now().isoformat()
    tracks[track_id]['total_distance'] = data.get('total_distance', 0)
    tracks[track_id]['map_image'] = data.get('map_image', None)
    
    return jsonify({'status': 'finished', 'track_id': track_id})

@app.route('/api/track/<track_id>/pdf', methods=['GET'])
def generate_pdf(track_id):
    """Generate PDF with the route map image"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    track = tracks[track_id]
    if len(track['points']) == 0:
        return jsonify({'error': 'No points in track'}), 400
    
    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Add title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "GPS Route Tracker")
    
    # Add metadata
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 90, f"Track ID: {track_id[:8]}")
    c.drawString(50, height - 110, f"Started: {track['started_at']}")
    c.drawString(50, height - 130, f"Finished: {track.get('finished_at', 'N/A')}")
    c.drawString(50, height - 150, f"Total Points: {len(track['points'])}")
    
    # Calculate route statistics
    lats = [p['lat'] for p in track['points']]
    lons = [p['lon'] for p in track['points']]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    
    total_distance = track.get('total_distance', 0)
    
    # Count filled points
    filled_count = sum(1 for p in track['points'] if p.get('filled', False))
    
    c.drawString(50, height - 180, f"Total Distance: {total_distance:.2f} km")
    if filled_count > 0:
        c.drawString(50, height - 200, f"Route-filled points: {filled_count} (realistic walking paths)")
    
    # Add route map image if available
    if track.get('map_image'):
        try:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, height - 240, "Route Map:")
            
            # Decode base64 image
            image_data = track['map_image'].split(',')[1]
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Save to temporary buffer
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Add image to PDF
            img_reader = ImageReader(img_buffer)
            img_width = 480
            img_height = 320
            
            c.drawImage(img_reader, 60, height - 600, width=img_width, height=img_height, 
                       preserveAspectRatio=True, mask='auto')
            
            # Add caption
            c.setFont("Helvetica", 9)
            c.drawString(60, height - 615, "Complete tracked route with realistic walking paths")
            
        except Exception as e:
            print(f"Error adding map image to PDF: {e}")
            c.setFont("Helvetica", 10)
            c.drawString(50, height - 260, "Map image not available")
    
    # Add footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 60, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(50, 45, "Powered by OpenStreetMap & OpenRouteService")
    c.drawString(50, 30, f"View at: https://www.openstreetmap.org/?mlat={center_lat}&mlon={center_lon}#map=15/{center_lat}/{center_lon}")
    
    c.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'route_{track_id[:8]}.pdf'
    )

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'tracks': len(tracks)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
