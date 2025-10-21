from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import uuid
import os

app = Flask(__name__)
CORS(app)

# Store tracks in memory
tracks = {}

# Enhanced HTML with beautiful design and robust GPS tracking
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
        
        /* Custom Leaflet styles */
        .leaflet-popup-content-wrapper {
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }
        
        .leaflet-popup-content {
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            margin: 15px;
        }
        
        /* Loading spinner */
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
        
        /* Mobile responsive */
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
        
        /* Toast notifications */
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
                    <p>Track your journey in real-time with OpenStreetMap</p>
                </div>
            </div>
        </div>
        
        <div class="alert alert-warning" id="alertBanner">
            <span id="alertMessage">📍 Please allow location access to start tracking your route.</span>
        </div>
        
        <div class="controls">
            <button class="btn btn-start" id="startBtn" onclick="startTracking()">
                <span class="btn-icon">▶</span>
                <span id="startBtnText">Start Tracking</span>
            </button>
            <button class="btn btn-stop" id="stopBtn" onclick="stopTracking()" disabled>
                <span class="btn-icon">⏹</span>
                <span>Finish</span>
            </button>
            <button class="btn btn-download" id="downloadBtn" onclick="downloadPDF()" disabled>
                <span class="btn-icon">⬇</span>
                <span>Download PDF</span>
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
    <script>
        let map, trackId = null, isTracking = false, watchId = null;
        let routePolyline = null, currentMarker = null, routePoints = [], totalDistance = 0;
        let startMarker = null, trackingStartTime = null, durationInterval = null;
        
        // Initialize map
        function initMap() {
            map = L.map('map').setView([20, 0], 2);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19
            }).addTo(map);
            
            // Try to get initial position
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        map.setView([lat, lon], 15);
                        
                        // Add marker for current location
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
            const R = 6371; // Earth's radius in km
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
                // Request permission first
                const permissionResult = await navigator.permissions.query({ name: 'geolocation' });
                
                if (permissionResult.state === 'denied') {
                    showAlert('Location permission denied. Please enable location access in your browser settings.', 'error');
                    startBtn.disabled = false;
                    startBtnText.textContent = 'Start Tracking';
                    return;
                }
                
                // Start tracking session
                const response = await fetch('/api/track/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error('Failed to start tracking session');
                }
                
                const data = await response.json();
                trackId = data.track_id;
                
                // Reset state
                routePoints = [];
                totalDistance = 0;
                trackingStartTime = Date.now();
                
                if (routePolyline) map.removeLayer(routePolyline);
                if (startMarker) map.removeLayer(startMarker);
                if (currentMarker) map.removeLayer(currentMarker);
                
                // Start watching position with high accuracy
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
        
        // Handle position update
        async function handlePosition(position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            
            console.log(`Position update: ${lat}, ${lon} (accuracy: ${accuracy}m)`);
            
            try {
                // Send point to backend
                const response = await fetch(`/api/track/${trackId}/point`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        lat: lat,
                        lon: lon,
                        accuracy: accuracy,
                        timestamp: new Date().toISOString()
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to save point');
                }
                
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
                
                // Calculate distance if we have a previous point
                if (routePoints.length > 0) {
                    const lastPoint = routePoints[routePoints.length - 1];
                    const distance = calculateDistance(lastPoint[0], lastPoint[1], lat, lon);
                    
                    // Only add point if movement is significant (more than 5 meters)
                    if (distance > 0.005 || routePoints.length === 1) {
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
                
                // Center map on current position (with smooth pan)
                map.panTo([lat, lon], {
                    animate: true,
                    duration: 0.5
                });
                
                // Update UI
                document.getElementById('pointCount').textContent = routePoints.length;
                document.getElementById('distance').textContent = totalDistance.toFixed(2) + ' km';
                
            } catch (error) {
                console.error('Error adding point:', error);
                showToast('Warning', 'Failed to save location point', 'warning');
            }
        }
        
        // Handle geolocation error
        function handleError(error) {
            console.error('Geolocation error:', error);
            let message = 'Error getting location: ';
            
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    message = 'Location permission denied. Please enable location access in your browser settings.';
                    showAlert(message, 'error');
                    stopTracking();
                    break;
                case error.POSITION_UNAVAILABLE:
                    message = 'Position unavailable. Please check your GPS signal.';
                    showToast('GPS Error', message, 'warning');
                    break;
                case error.TIMEOUT:
                    message = 'Location request timed out. Retrying...';
                    console.log(message);
                    break;
                default:
                    message = 'Unknown error occurred while getting location.';
                    showToast('Error', message, 'error');
            }
        }
        
        // Stop tracking
        async function stopTracking() {
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
                    const response = await fetch(`/api/track/${trackId}/finish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    if (!response.ok) {
                        throw new Error('Failed to finish tracking');
                    }
                    
                    showToast('Tracking Finished', `Total distance: ${totalDistance.toFixed(2)} km`);
                    
                } catch (error) {
                    console.error('Error finishing track:', error);
                    showToast('Warning', 'Failed to save final track data', 'warning');
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
            downloadBtn.innerHTML = '<span class="spinner"></span> Generating PDF...';
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
                startBtnText.textContent = 'Tracking...';
                stopBtn.disabled = false;
                downloadBtn.disabled = true;
                statusText.innerHTML = '<span class="tracking-indicator active"></span>Tracking';
                statusText.className = 'status-value active';
            } else {
                startBtn.disabled = false;
                startBtnText.textContent = 'Start Tracking';
                stopBtn.disabled = true;
                downloadBtn.disabled = trackId === null;
                statusText.innerHTML = '<span class="tracking-indicator"></span>' + (trackId ? 'Finished' : 'Inactive');
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
        function showToast(title, message, type = 'success') {
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
            console.log('GPS Tracker initialized');
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
        'finished': False
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
        'accuracy': data.get('accuracy', None)
    }
    
    tracks[track_id]['points'].append(point)
    return jsonify({'status': 'point_added', 'total_points': len(tracks[track_id]['points'])})

@app.route('/api/track/<track_id>/finish', methods=['POST'])
def finish_track(track_id):
    """Finish tracking"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    tracks[track_id]['finished'] = True
    tracks[track_id]['finished_at'] = datetime.now().isoformat()
    
    return jsonify({'status': 'finished', 'track_id': track_id})

@app.route('/api/track/<track_id>/pdf', methods=['GET'])
def generate_pdf(track_id):
    """Generate PDF with the route map"""
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
    
    # Calculate total distance
    total_distance = 0
    for i in range(1, len(track['points'])):
        p1 = track['points'][i-1]
        p2 = track['points'][i]
        # Haversine formula
        R = 6371
        dLat = (p2['lat'] - p1['lat']) * 3.14159 / 180
        dLon = (p2['lon'] - p1['lon']) * 3.14159 / 180
        a = (0.5 - 0.5 * ((1 - dLat * dLat / 2) * (1 - dLat * dLat / 2))) + \
            (1 - p1['lat'] * p1['lat'] * 3.14159 * 3.14159 / 32400) * \
            (1 - p2['lat'] * p2['lat'] * 3.14159 * 3.14159 / 32400) * \
            (0.5 - 0.5 * ((1 - dLon * dLon / 2) * (1 - dLon * dLon / 2)))
        total_distance += 2 * R * (0.7071 if a < 0 else (1.4142 * (a ** 0.5) if a > 1 else 2 * (a ** 0.5)))
    
    c.drawString(50, height - 180, f"Center: {center_lat:.6f}, {center_lon:.6f}")
    c.drawString(50, height - 200, f"Total Distance: {total_distance:.2f} km")
    
    # Add route coordinates header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 240, "Route Coordinates:")
    
    # Add coordinates
    c.setFont("Helvetica", 9)
    y_pos = height - 260
    for i, point in enumerate(track['points'][:15]):
        c.drawString(60, y_pos, f"{i+1}. Lat: {point['lat']:.6f}, Lon: {point['lon']:.6f}")
        y_pos -= 15
        if y_pos < 100:
            break
    
    if len(track['points']) > 15:
        c.drawString(60, y_pos - 10, f"... and {len(track['points']) - 15} more points")
    
    # Add footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 60, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(50, 45, "Powered by OpenStreetMap")
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
