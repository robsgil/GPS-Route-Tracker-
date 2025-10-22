from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import uuid
import os
import requests
import math

app = Flask(__name__)
CORS(app)

# Store tracks in memory
tracks = {}

# Catalan UI with pause button
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="ca">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rastrejador de Rutes GPS</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 100%; height: 100vh; display: flex; flex-direction: column; }
        .header { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); padding: 20px 30px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); border-bottom: 3px solid #667eea; }
        .header-content { display: flex; align-items: center; gap: 15px; }
        .logo { font-size: 40px; animation: bounce 2s infinite; }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        .header-text h1 { font-size: 28px; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; }
        .header-text p { font-size: 14px; color: #666; font-weight: 500; }
        .controls { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); padding: 25px 30px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
        .btn { padding: 14px 28px; font-size: 16px; border: none; border-radius: 12px; cursor: pointer; font-weight: 600; transition: all 0.3s ease; display: flex; align-items: center; gap: 10px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15); text-transform: uppercase; letter-spacing: 0.5px; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
        .btn:active:not(:disabled) { transform: scale(0.95); }
        .btn-icon { font-size: 20px; }
        .btn-start { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
        .btn-start:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 25px rgba(17, 153, 142, 0.4); }
        .btn-pause { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
        .btn-pause:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 25px rgba(240, 147, 251, 0.4); }
        .btn-stop { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; }
        .btn-stop:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 25px rgba(235, 51, 73, 0.4); }
        .btn-download { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-download:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 25px rgba(102, 126, 234, 0.4); }
        .status { flex: 1; display: flex; gap: 30px; font-size: 14px; min-width: 300px; }
        .status-item { display: flex; flex-direction: column; padding: 10px 15px; background: rgba(102, 126, 234, 0.1); border-radius: 10px; min-width: 100px; }
        .status-label { font-size: 11px; color: #888; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
        .status-value { font-weight: 700; font-size: 20px; color: #333; }
        .status-value.active { color: #11998e; }
        .status-value.paused { color: #f5576c; }
        .status-value.inactive { color: #eb3349; }
        #map { flex: 1; min-height: 400px; box-shadow: inset 0 4px 20px rgba(0, 0, 0, 0.1); }
        .alert { padding: 15px 30px; font-size: 14px; font-weight: 500; display: none; animation: slideDown 0.3s ease; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        .alert-warning { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
        .alert-success { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
        .alert-error { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; }
        .tracking-indicator { width: 12px; height: 12px; border-radius: 50%; background: #eb3349; display: inline-block; margin-right: 8px; box-shadow: 0 0 10px rgba(235, 51, 73, 0.5); }
        .tracking-indicator.active { background: #11998e; animation: pulse 2s infinite; box-shadow: 0 0 20px rgba(17, 153, 142, 0.8); }
        .tracking-indicator.paused { background: #f5576c; animation: blink 1s infinite; box-shadow: 0 0 15px rgba(245, 87, 108, 0.8); }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.7; transform: scale(1.2); } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255, 255, 255, 0.3); border-radius: 50%; border-top-color: white; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) {
            .header { padding: 15px 20px; }
            .header-text h1 { font-size: 22px; }
            .controls { flex-direction: column; align-items: stretch; padding: 20px; }
            .status { flex-direction: column; gap: 10px; width: 100%; }
            .btn { width: 100%; justify-content: center; }
        }
        .toast { position: fixed; bottom: 30px; right: 30px; background: white; padding: 20px 25px; border-radius: 12px; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2); display: none; z-index: 10000; animation: slideUp 0.3s ease; max-width: 400px; }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .toast.show { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <div class="logo">🗺️</div>
                <div class="header-text">
                    <h1>Rastrejador de Rutes GPS</h1>
                    <p>Segueix el teu recorregut en temps real amb OpenStreetMap</p>
                </div>
            </div>
        </div>
        <div class="alert alert-warning" id="alertBanner">
            <span id="alertMessage">📍 Si us plau, permet l'accés a la ubicació per començar el seguiment.</span>
        </div>
        <div class="controls">
            <button class="btn btn-start" id="startBtn" onclick="startTracking()">
                <span class="btn-icon">▶</span>
                <span id="startBtnText">Iniciar</span>
            </button>
            <button class="btn btn-pause" id="pauseBtn" onclick="togglePause()" disabled>
                <span class="btn-icon" id="pauseIcon">⏸</span>
                <span id="pauseBtnText">Pausar</span>
            </button>
            <button class="btn btn-stop" id="stopBtn" onclick="stopTracking()" disabled>
                <span class="btn-icon">⏹</span>
                <span>Finalitzar</span>
            </button>
            <button class="btn btn-download" id="downloadBtn" onclick="downloadPDF()" disabled>
                <span class="btn-icon">⬇</span>
                <span id="downloadBtnText">Descarregar PDF</span>
            </button>
            <div class="status">
                <div class="status-item">
                    <span class="status-label">Estat</span>
                    <span class="status-value inactive" id="statusText">
                        <span class="tracking-indicator" id="indicator"></span>
                        Inactiu
                    </span>
                </div>
                <div class="status-item">
                    <span class="status-label">Punts</span>
                    <span class="status-value" id="pointCount">0</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Distància</span>
                    <span class="status-value" id="distance">0,00 km</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Durada</span>
                    <span class="status-value" id="duration">00:00</span>
                </div>
            </div>
        </div>
        <div id="map"></div>
    </div>
    <div class="toast" id="toast">
        <strong id="toastTitle">Notificació</strong>
        <p id="toastMessage"></p>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map, trackId = null, isTracking = false, isPaused = false, watchId = null;
        let routePolyline = null, currentMarker = null, routePoints = [], totalDistance = 0;
        let startMarker = null, trackingStartTime = null, durationInterval = null;
        let pausedTime = 0, pauseStartTime = null;
        
        function initMap() {
            map = L.map('map').setView([20, 0], 2);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contribuïdors',
                maxZoom: 19
            }).addTo(map);
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        map.setView([position.coords.latitude, position.coords.longitude], 15);
                        L.circleMarker([position.coords.latitude, position.coords.longitude], {
                            radius: 8, fillColor: '#667eea', color: '#fff', weight: 2, opacity: 1, fillOpacity: 0.8
                        }).addTo(map).bindPopup('La teva ubicació actual');
                        showToast('Ubicació trobada', 'A punt per començar el seguiment!');
                    },
                    (error) => showAlert('No es pot obtenir la teva ubicació. Assegura\'t que els serveis d\'ubicació estiguin activats.', 'warning')
                );
            } else {
                showAlert('La geolocalització no està suportada pel teu navegador', 'error');
            }
        }
        
        function calculateDistance(lat1, lon1, lat2, lon2) {
            const R = 6371;
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
            return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }
        
        function updateDuration() {
            if (!trackingStartTime) return;
            const elapsed = Math.floor((Date.now() - trackingStartTime - pausedTime) / 1000);
            document.getElementById('duration').textContent = String(Math.floor(elapsed / 60)).padStart(2, '0') + ':' + String(elapsed % 60).padStart(2, '0');
        }
        
        async function startTracking() {
            if (!navigator.geolocation) {
                showAlert('La geolocalització no està suportada pel teu navegador', 'error');
                return;
            }
            const startBtn = document.getElementById('startBtn');
            const startBtnText = document.getElementById('startBtnText');
            startBtn.disabled = true;
            startBtnText.innerHTML = '<span class="spinner"></span> Inicialitzant...';
            showAlert('Sol·licitant permís d\'ubicació...', 'warning');
            try {
                const response = await fetch('/api/track/start', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                if (!response.ok) throw new Error('Error al iniciar el seguiment');
                const data = await response.json();
                trackId = data.track_id;
                routePoints = [];
                totalDistance = 0;
                pausedTime = 0;
                trackingStartTime = Date.now();
                if (routePolyline) map.removeLayer(routePolyline);
                if (startMarker) map.removeLayer(startMarker);
                if (currentMarker) map.removeLayer(currentMarker);
                watchId = navigator.geolocation.watchPosition(handlePosition, handleError, { enableHighAccuracy: true, maximumAge: 1000, timeout: 10000 });
                isTracking = true;
                isPaused = false;
                updateUI();
                durationInterval = setInterval(updateDuration, 1000);
                hideAlert();
                showToast('Seguiment iniciat', 'La teva ruta s\'està enregistrant!');
            } catch (error) {
                showAlert('Error al iniciar el seguiment. Si us plau, torna-ho a provar.', 'error');
                startBtn.disabled = false;
                startBtnText.textContent = 'Iniciar';
            }
        }
        
        function togglePause() {
            if (!isTracking) return;
            isPaused = !isPaused;
            const pauseIcon = document.getElementById('pauseIcon');
            const pauseBtnText = document.getElementById('pauseBtnText');
            if (isPaused) {
                pauseStartTime = Date.now();
                pauseIcon.textContent = '▶';
                pauseBtnText.textContent = 'Reprendre';
                showToast('Seguiment pausat', 'Prem "Reprendre" per continuar');
            } else {
                if (pauseStartTime) {
                    pausedTime += (Date.now() - pauseStartTime);
                    pauseStartTime = null;
                }
                pauseIcon.textContent = '⏸';
                pauseBtnText.textContent = 'Pausar';
                showToast('Seguiment reprès', 'La ruta continua enregistrant-se');
            }
            updateUI();
        }
        
        async function handlePosition(position) {
            if (isPaused) return;
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            try {
                await fetch(`/api/track/${trackId}/point`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lat, lon, accuracy: position.coords.accuracy, timestamp: new Date().toISOString() })
                });
                const newPoint = [lat, lon];
                if (routePoints.length === 0) {
                    startMarker = L.marker([lat, lon], {
                        icon: L.divIcon({
                            className: 'start-marker',
                            html: '<div style="background: #11998e; color: white; padding: 8px 12px; border-radius: 20px; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">INICI</div>',
                            iconSize: [60, 30]
                        })
                    }).addTo(map);
                    map.setView([lat, lon], 16);
                }
                if (routePoints.length > 0) {
                    const lastPoint = routePoints[routePoints.length - 1];
                    const distance = calculateDistance(lastPoint[0], lastPoint[1], lat, lon);
                    if (distance > 0.005 || routePoints.length === 1) totalDistance += distance;
                }
                routePoints.push(newPoint);
                if (routePolyline) map.removeLayer(routePolyline);
                routePolyline = L.polyline(routePoints, { color: '#667eea', weight: 5, opacity: 0.8, smoothFactor: 1 }).addTo(map);
                if (currentMarker) map.removeLayer(currentMarker);
                currentMarker = L.circleMarker([lat, lon], { radius: 10, fillColor: '#11998e', color: '#fff', weight: 3, opacity: 1, fillOpacity: 1 }).addTo(map);
                L.circle([lat, lon], { radius: position.coords.accuracy, fillColor: '#11998e', fillOpacity: 0.1, color: '#11998e', weight: 1, opacity: 0.3 }).addTo(map);
                map.panTo([lat, lon], { animate: true, duration: 0.5 });
                document.getElementById('pointCount').textContent = routePoints.length;
                document.getElementById('distance').textContent = totalDistance.toFixed(2).replace('.', ',') + ' km';
            } catch (error) {
                showToast('Avís', 'Error al desar el punt d\'ubicació', 'warning');
            }
        }
        
        function handleError(error) {
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    showAlert('Permís d\'ubicació denegat. Si us plau, activa l\'accés a la ubicació a la configuració del navegador.', 'error');
                    stopTracking();
                    break;
                case error.POSITION_UNAVAILABLE:
                    showToast('Error GPS', 'Posició no disponible. Si us plau, comprova el senyal GPS.', 'warning');
                    break;
            }
        }
        
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
                    const mapBounds = map.getBounds();
                    const center = map.getCenter();
                    await fetch(`/api/track/${trackId}/finish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            bounds: { north: mapBounds.getNorth(), south: mapBounds.getSouth(), east: mapBounds.getEast(), west: mapBounds.getWest() },
                            center: { lat: center.lat, lng: center.lng },
                            zoom: map.getZoom(),
                            total_distance: totalDistance
                        })
                    });
                    showToast('Seguiment finalitzat', `Distància total: ${totalDistance.toFixed(2)} km`);
                } catch (error) {
                    showToast('Avís', 'Error al desar les dades finals', 'warning');
                }
            }
            isTracking = false;
            isPaused = false;
            updateUI();
        }
        
        async function downloadPDF() {
            if (!trackId) {
                showAlert('No hi ha cap ruta disponible per descarregar', 'error');
                return;
            }
            const downloadBtn = document.getElementById('downloadBtn');
            const originalText = downloadBtn.innerHTML;
            downloadBtn.innerHTML = '<span class="btn-icon">⬇</span><span class="spinner"></span> Generant PDF...';
            downloadBtn.disabled = true;
            try {
                window.location.href = `/api/track/${trackId}/pdf`;
                showToast('Èxit', 'Descàrrega del PDF iniciada!');
                setTimeout(() => {
                    downloadBtn.innerHTML = originalText;
                    downloadBtn.disabled = false;
                }, 2000);
            } catch (error) {
                showAlert('Error al descarregar el PDF. Si us plau, torna-ho a provar.', 'error');
                downloadBtn.innerHTML = originalText;
                downloadBtn.disabled = false;
            }
        }
        
        function updateUI() {
            const startBtn = document.getElementById('startBtn');
            const startBtnText = document.getElementById('startBtnText');
            const pauseBtn = document.getElementById('pauseBtn');
            const stopBtn = document.getElementById('stopBtn');
            const downloadBtn = document.getElementById('downloadBtn');
            const statusText = document.getElementById('statusText');
            if (isTracking) {
                startBtn.disabled = true;
                pauseBtn.disabled = false;
                stopBtn.disabled = false;
                downloadBtn.disabled = true;
                if (isPaused) {
                    statusText.innerHTML = '<span class="tracking-indicator paused"></span>Pausat';
                    statusText.className = 'status-value paused';
                } else {
                    startBtnText.textContent = 'Enregistrant...';
                    statusText.innerHTML = '<span class="tracking-indicator active"></span>Enregistrant';
                    statusText.className = 'status-value active';
                }
            } else {
                startBtn.disabled = false;
                startBtnText.textContent = 'Iniciar';
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                downloadBtn.disabled = trackId === null;
                statusText.innerHTML = '<span class="tracking-indicator"></span>' + (trackId ? 'Finalitzat' : 'Inactiu');
                statusText.className = 'status-value ' + (trackId ? 'active' : 'inactive');
            }
        }
        
        function showAlert(message, type = 'warning') {
            const banner = document.getElementById('alertBanner');
            banner.className = 'alert alert-' + type;
            document.getElementById('alertMessage').textContent = message;
            banner.style.display = 'block';
        }
        
        function hideAlert() {
            document.getElementById('alertBanner').style.display = 'none';
        }
        
        function showToast(title, message) {
            const toast = document.getElementById('toast');
            document.getElementById('toastTitle').textContent = title;
            document.getElementById('toastMessage').textContent = message;
            toast.className = 'toast show';
            setTimeout(() => toast.classList.remove('show'), 4000);
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
    return Response(HTML_CONTENT, mimetype='text/html')

@app.route('/api/track/start', methods=['POST'])
def start_track():
    track_id = str(uuid.uuid4())
    tracks[track_id] = {
        'id': track_id,
        'started_at': datetime.now().isoformat(),
        'points': [],
        'finished': False,
        'map_data': None
    }
    return jsonify({'track_id': track_id, 'status': 'started'})

@app.route('/api/track/<track_id>/point', methods=['POST'])
def add_point(track_id):
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    data = request.json
    tracks[track_id]['points'].append({
        'lat': data['lat'],
        'lon': data['lon'],
        'timestamp': data.get('timestamp', datetime.now().isoformat()),
        'accuracy': data.get('accuracy', None)
    })
    return jsonify({'status': 'point_added', 'total_points': len(tracks[track_id]['points'])})

@app.route('/api/track/<track_id>/finish', methods=['POST'])
def finish_track(track_id):
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    data = request.json
    tracks[track_id]['finished'] = True
    tracks[track_id]['finished_at'] = datetime.now().isoformat()
    tracks[track_id]['map_data'] = data
    return jsonify({'status': 'finished', 'track_id': track_id})

@app.route('/api/track/<track_id>/pdf', methods=['GET'])
def generate_pdf(track_id):
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    track = tracks[track_id]
    if len(track['points']) == 0:
        return jsonify({'error': 'No points in track'}), 400
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "Rastrejador de Rutes GPS")
    
    # Metadata
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 90, f"ID de Ruta: {track_id[:8]}")
    c.drawString(50, height - 110, f"Inici: {format_catalan_date(track['started_at'])}")
    c.drawString(50, height - 130, f"Final: {format_catalan_date(track.get('finished_at', 'N/A'))}")
    c.drawString(50, height - 150, f"Total de Punts: {len(track['points'])}")
    
    # Calculate stats
    lats = [p['lat'] for p in track['points']]
    lons = [p['lon'] for p in track['points']]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = max(lons), min(lons)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    # Calculate distance
    total_distance = 0
    for i in range(1, len(track['points'])):
        p1, p2 = track['points'][i-1], track['points'][i]
        total_distance += calculateDistance(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
    
    c.drawString(50, height - 180, f"Distància Total: {total_distance:.2f} km")
    c.drawString(50, height - 200, f"Centre: {center_lat:.6f}, {center_lon:.6f}")
    
    # Map visualization section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 240, "Visualització de la Ruta:")
    
    # Draw map box
    map_x, map_y = 50, height - 600
    map_width, map_height = 500, 330
    c.setStrokeColor(colors.HexColor('#667eea'))
    c.setLineWidth(2)
    c.rect(map_x, map_y, map_width, map_height, stroke=1, fill=0)
    
    # Draw route path on the map
    if len(track['points']) > 1:
        # Normalize coordinates to fit in the box
        lat_range = max_lat - min_lat if max_lat != min_lat else 0.001
        lon_range = max_lon - min_lon if max_lon != min_lon else 0.001
        
        c.setStrokeColor(colors.HexColor('#667eea'))
        c.setLineWidth(3)
        
        path = c.beginPath()
        first_point = True
        for point in track['points']:
            # Map coordinates to box
            x = map_x + 30 + ((point['lon'] - min_lon) / lon_range) * (map_width - 60)
            y = map_y + 30 + ((point['lat'] - min_lat) / lat_range) * (map_height - 60)
            if first_point:
                path.moveTo(x, y)
                first_point = False
            else:
                path.lineTo(x, y)
        c.drawPath(path, stroke=1, fill=0)
        
        # Draw start marker
        start = track['points'][0]
        start_x = map_x + 30 + ((start['lon'] - min_lon) / lon_range) * (map_width - 60)
        start_y = map_y + 30 + ((start['lat'] - min_lat) / lat_range) * (map_height - 60)
        c.setFillColor(colors.HexColor('#11998e'))
        c.circle(start_x, start_y, 5, stroke=0, fill=1)
        
        # Draw end marker
        end = track['points'][-1]
        end_x = map_x + 30 + ((end['lon'] - min_lon) / lon_range) * (map_width - 60)
        end_y = map_y + 30 + ((end['lat'] - min_lat) / lat_range) * (map_height - 60)
        c.setFillColor(colors.HexColor('#eb3349'))
        c.circle(end_x, end_y, 5, stroke=0, fill=1)
    
    # Legend
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(map_x + 10, map_y - 15, "● Inici")
    c.drawString(map_x + 70, map_y - 15, "● Final")
    c.drawString(map_x + 130, map_y - 15, "— Ruta")
    
    # OpenStreetMap link
    zoom = calculateZoom(max_lat - min_lat, max_lon - min_lon)
    osm_link = f"https://www.openstreetmap.org/?mlat={center_lat}&mlon={center_lon}#map={zoom}/{center_lat}/{center_lon}"
    c.setFont("Helvetica", 9)
    c.drawString(50, map_y - 35, "Veure ruta completa a OpenStreetMap:")
    c.setFillColor(colors.HexColor('#667eea'))
    c.drawString(50, map_y - 50, osm_link)
    
    # Footer
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 60, f"Generat el {format_catalan_date(datetime.now().isoformat())}")
    c.drawString(50, 45, "Amb tecnologia d'OpenStreetMap")
    
    c.save()
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'ruta_{track_id[:8]}.pdf')

def format_catalan_date(iso_date):
    if iso_date == 'N/A':
        return 'N/A'
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        months = ['gener', 'febrer', 'març', 'abril', 'maig', 'juny', 'juliol', 'agost', 'setembre', 'octubre', 'novembre', 'desembre']
        return f"{dt.day} de {months[dt.month-1]} de {dt.year}, {dt.hour:02d}:{dt.minute:02d}"
    except:
        return iso_date

def calculateDistance(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = (lat2 - lat1) * math.pi / 180
    dLon = (lon2 - lon1) * math.pi / 180
    a = math.sin(dLat/2) ** 2 + math.cos(lat1 * math.pi / 180) * math.cos(lat2 * math.pi / 180) * math.sin(dLon/2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calculateZoom(lat_diff, lon_diff):
    max_diff = max(lat_diff, lon_diff)
    if max_diff < 0.01:
        return 16
    elif max_diff < 0.05:
        return 14
    elif max_diff < 0.1:
        return 13
    else:
        return 12

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'tracks': len(tracks)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
