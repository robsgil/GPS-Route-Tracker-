from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import json
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import uuid

app = Flask(__name__)
CORS(app)

# Store tracks in memory (for MVP - in production, use a database)
tracks = {}

# Embedded HTML - No templates folder needed!
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPS Route Tracker - MVP</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; background: #f5f5f5; }
        .container { max-width: 100%; height: 100vh; display: flex; flex-direction: column; }
        .header { background: #2c3e50; color: white; padding: 15px 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header h1 { font-size: 24px; margin-bottom: 5px; }
        .header p { font-size: 14px; opacity: 0.9; }
        .controls { background: white; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
        .btn { padding: 12px 24px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s; display: flex; align-items: center; gap: 8px; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-start { background: #27ae60; color: white; }
        .btn-start:hover:not(:disabled) { background: #229954; }
        .btn-stop { background: #e74c3c; color: white; }
        .btn-stop:hover:not(:disabled) { background: #c0392b; }
        .btn-download { background: #3498db; color: white; }
        .btn-download:hover:not(:disabled) { background: #2980b9; }
        .status { flex: 1; display: flex; gap: 20px; font-size: 14px; color: #555; }
        .status-item { display: flex; flex-direction: column; }
        .status-label { font-size: 12px; color: #999; margin-bottom: 2px; }
        .status-value { font-weight: 600; font-size: 16px; }
        .status-value.active { color: #27ae60; }
        .status-value.inactive { color: #e74c3c; }
        #map { flex: 1; min-height: 400px; }
        .info-banner { background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 0; font-size: 14px; }
        .tracking-indicator { width: 12px; height: 12px; border-radius: 50%; background: #e74c3c; display: inline-block; margin-right: 8px; }
        .tracking-indicator.active { background: #27ae60; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @media (max-width: 768px) {
            .controls { flex-direction: column; align-items: stretch; }
            .status { flex-direction: column; gap: 10px; }
            .btn { width: 100%; justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗺️ GPS Route Tracker</h1>
            <p>Track your route in real-time using OpenStreetMap</p>
        </div>
        <div class="info-banner" id="permissionBanner" style="display: none;">
            📍 Please allow location access to start tracking your route.
        </div>
        <div class="controls">
            <button class="btn btn-start" id="startBtn" onclick="startTracking()">
                <span>▶</span> Start Tracking
            </button>
            <button class="btn btn-stop" id="stopBtn" onclick="stopTracking()" disabled>
                <span>⏹</span> Finish
            </button>
            <button class="btn btn-download" id="downloadBtn" onclick="downloadPDF()" disabled>
                <span>⬇</span> Download PDF
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
                    <span class="status-label">Points Tracked</span>
                    <span class="status-value" id="pointCount">0</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Distance</span>
                    <span class="status-value" id="distance">0.00 km</span>
                </div>
            </div>
        </div>
        <div id="map"></div>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map, trackId = null, isTracking = false, watchId = null;
        let routePolyline = null, currentMarker = null, routePoints = [], totalDistance = 0;
        
        function initMap() {
            map = L.map('map').setView([0, 0], 2);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(map);
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        map.setView([lat, lon], 15);
                    },
                    (error) => console.log('Initial position error:', error)
                );
            }
        }
        
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
        
        async function startTracking() {
            if (!navigator.geolocation) {
                alert('Geolocation is not supported by your browser');
                return;
            }
            document.getElementById('permissionBanner').style.display = 'block';
            try {
                const response = await fetch('/api/track/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                trackId = data.track_id;
                routePoints = [];
                totalDistance = 0;
                if (routePolyline) map.removeLayer(routePolyline);
                watchId = navigator.geolocation.watchPosition(
                    handlePosition, handleError,
                    { enableHighAccuracy: true, maximumAge: 0, timeout: 5000 }
                );
                isTracking = true;
                updateUI();
                document.getElementById('permissionBanner').style.display = 'none';
            } catch (error) {
                console.error('Error starting track:', error);
                alert('Failed to start tracking. Please try again.');
                document.getElementById('permissionBanner').style.display = 'none';
            }
        }
        
        async function handlePosition(position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            try {
                await fetch(`/api/track/${trackId}/point`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lat, lon, accuracy, timestamp: new Date().toISOString() })
                });
                const newPoint = [lat, lon];
                if (routePoints.length > 0) {
                    const lastPoint = routePoints[routePoints.length - 1];
                    const distance = calculateDistance(lastPoint[0], lastPoint[1], lat, lon);
                    totalDistance += distance;
                }
                routePoints.push(newPoint);
                if (routePolyline) map.removeLayer(routePolyline);
                routePolyline = L.polyline(routePoints, {
                    color: '#3498db', weight: 4, opacity: 0.7
                }).addTo(map);
                if (currentMarker) map.removeLayer(currentMarker);
                currentMarker = L.circleMarker([lat, lon], {
                    radius: 8, fillColor: '#27ae60', color: '#fff',
                    weight: 2, opacity: 1, fillOpacity: 0.8
                }).addTo(map);
                map.setView([lat, lon], map.getZoom());
                document.getElementById('pointCount').textContent = routePoints.length;
                document.getElementById('distance').textContent = totalDistance.toFixed(2) + ' km';
            } catch (error) {
                console.error('Error adding point:', error);
            }
        }
        
        function handleError(error) {
            console.error('Geolocation error:', error);
            let message = 'Error getting location: ';
            switch(error.code) {
                case error.PERMISSION_DENIED: message += 'Permission denied. Please allow location access.'; break;
                case error.POSITION_UNAVAILABLE: message += 'Position unavailable.'; break;
                case error.TIMEOUT: message += 'Request timeout.'; break;
                default: message += 'Unknown error.';
            }
            document.getElementById('permissionBanner').textContent = message;
            document.getElementById('permissionBanner').style.display = 'block';
        }
        
        async function stopTracking() {
            if (watchId) {
                navigator.geolocation.clearWatch(watchId);
                watchId = null;
            }
            if (trackId) {
                try {
                    await fetch(`/api/track/${trackId}/finish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                } catch (error) {
                    console.error('Error finishing track:', error);
                }
            }
            isTracking = false;
            updateUI();
        }
        
        function downloadPDF() {
            if (!trackId) {
                alert('No track available to download');
                return;
            }
            try {
                window.location.href = `/api/track/${trackId}/pdf`;
            } catch (error) {
                console.error('Error downloading PDF:', error);
                alert('Failed to download PDF. Please try again.');
            }
        }
        
        function updateUI() {
            const startBtn = document.getElementById('startBtn');
            const stopBtn = document.getElementById('stopBtn');
            const downloadBtn = document.getElementById('downloadBtn');
            const statusText = document.getElementById('statusText');
            if (isTracking) {
                startBtn.disabled = true;
                stopBtn.disabled = false;
                downloadBtn.disabled = true;
                statusText.innerHTML = '<span class="tracking-indicator active" id="indicator"></span>Tracking';
                statusText.className = 'status-value active';
            } else {
                startBtn.disabled = false;
                stopBtn.disabled = true;
                downloadBtn.disabled = trackId === null;
                statusText.innerHTML = '<span class="tracking-indicator"></span>' + (trackId ? 'Finished' : 'Inactive');
                statusText.className = 'status-value ' + (trackId ? 'active' : 'inactive');
            }
        }
        
        document.addEventListener('DOMContentLoaded', function() {
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
    """Finish tracking and generate PDF"""
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
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "GPS Route Tracker")
    
    # Add metadata
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Track ID: {track_id[:8]}")
    c.drawString(50, height - 100, f"Started: {track['started_at']}")
    c.drawString(50, height - 120, f"Total Points: {len(track['points'])}")
    
    # Calculate route bounds
    lats = [p['lat'] for p in track['points']]
    lons = [p['lon'] for p in track['points']]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    c.drawString(50, height - 140, f"Center: {center_lat:.6f}, {center_lon:.6f}")
    c.drawString(50, height - 180, "Route Coordinates:")
    
    y_pos = height - 200
    for i, point in enumerate(track['points'][:10]):
        c.setFont("Helvetica", 9)
        c.drawString(60, y_pos, f"{i+1}. Lat: {point['lat']:.6f}, Lon: {point['lon']:.6f}")
        y_pos -= 15
        if y_pos < 100:
            break
    
    if len(track['points']) > 10:
        c.drawString(60, y_pos - 10, f"... and {len(track['points']) - 10} more points")
    
    # Add footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 50, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(50, 35, "Powered by OpenStreetMap")
    
    c.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'route_{track_id[:8]}.pdf'
    )

@app.route('/api/track/<track_id>', methods=['GET'])
def get_track(track_id):
    """Get track data"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    return jsonify(tracks[track_id])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
