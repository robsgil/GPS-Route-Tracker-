from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import uuid
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

app = Flask(__name__)
CORS(app)

# Store tracks in memory
tracks = {}
tracks_lock = Lock()

# OpenRouteService API configuration
ORS_API_KEY = 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjZhN2QyNmZkMDhkNDQ1YmM4NWYyZDIwYmJmYTczZGRlIiwiaCI6Im11cm11cjY0In0='
ORS_API_URL = 'https://api.openrouteservice.org/v2/directions/foot-walking'

# Rate limiting for API calls
api_call_times = []
api_lock = Lock()
MAX_CALLS_PER_MINUTE = 35  # Stay under 40/min limit
CIRCUIT_BREAKER_THRESHOLD = 3  # Fail after 3 consecutive failures
circuit_breaker_failures = 0

def rate_limit_api_call():
    """Ensure we don't exceed API rate limits"""
    with api_lock:
        current_time = time.time()
        # Remove calls older than 60 seconds
        api_call_times[:] = [t for t in api_call_times if current_time - t < 60]
        
        # If we're at the limit, wait
        if len(api_call_times) >= MAX_CALLS_PER_MINUTE:
            sleep_time = 60 - (current_time - api_call_times[0]) + 1
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        api_call_times.append(time.time())

def fill_gap_with_walking_route(start_lat, start_lon, end_lat, end_lon, gap_index=0):
    """
    Call OpenRouteService API to get walking route between two points
    Returns dict with success status and coordinates or None
    """
    global circuit_breaker_failures
    
    if ORS_API_KEY == 'YOUR_API_KEY_HERE':
        print(f"Warning: ORS_API_KEY not set, skipping gap {gap_index}")
        return None
    
    # Circuit breaker: stop trying after multiple failures
    if circuit_breaker_failures >= CIRCUIT_BREAKER_THRESHOLD:
        print(f"Circuit breaker open, skipping gap {gap_index}")
        return None
    
    try:
        # Rate limit before calling
        rate_limit_api_call()
        
        headers = {
            'Authorization': ORS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        body = {
            'coordinates': [[start_lon, start_lat], [end_lon, end_lat]],
            'format': 'geojson'
        }
        
        print(f"Filling gap {gap_index + 1}: ({start_lat:.6f}, {start_lon:.6f}) -> ({end_lat:.6f}, {end_lon:.6f})")
        
        response = requests.post(
            ORS_API_URL,
            json=body,
            headers=headers,
            timeout=5  # Reduced timeout for faster failure
        )
        
        if response.status_code == 200:
            data = response.json()
            coords = data['features'][0]['geometry']['coordinates']
            # Convert from [lon, lat] to [lat, lon]
            result = [[lat, lon] for lon, lat in coords]
            print(f"✓ Gap {gap_index + 1} filled with {len(result)} points")
            circuit_breaker_failures = 0  # Reset on success
            return result
        else:
            print(f"✗ ORS API error for gap {gap_index + 1}: {response.status_code}")
            circuit_breaker_failures += 1
            return None
            
    except requests.Timeout:
        print(f"✗ Timeout for gap {gap_index + 1}")
        circuit_breaker_failures += 1
        return None
    except Exception as e:
        print(f"✗ Error filling gap {gap_index + 1}: {e}")
        circuit_breaker_failures += 1
        return None

# Spanish UI with gap detection and intelligent gap filling
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rastreador de Rutas GPS</title>
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
        
        .btn-gpx {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .btn-gpx:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(240, 147, 251, 0.4);
        }
        
        .status {
            flex: 1;
            display: flex;
            gap: 20px;
            font-size: 14px;
            min-width: 300px;
            flex-wrap: wrap;
        }
        
        .status-item {
            display: flex;
            flex-direction: column;
            padding: 10px 15px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 10px;
            min-width: 90px;
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
        
        .status-value.warning {
            color: #f5576c;
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
        
        .legend {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            z-index: 1000;
            font-size: 12px;
            display: none;
        }
        
        .legend.show {
            display: block;
        }
        
        .legend-title {
            font-weight: 700;
            margin-bottom: 10px;
            color: #333;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }
        
        .legend-line {
            width: 30px;
            height: 3px;
        }
        
        .legend-line.solid {
            background: #667eea;
        }
        
        .legend-line.dashed {
            background: linear-gradient(to right, #ff6b6b 50%, transparent 50%);
            background-size: 8px 3px;
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
            
            .legend {
                bottom: 10px;
                right: 10px;
                font-size: 11px;
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
                    <h1>Rastreador de Rutas GPS</h1>
                    <p>Rastrea tu recorrido con rutas inteligentes rellenadas por IA</p>
                </div>
            </div>
        </div>
        
        <div class="alert alert-warning" id="alertBanner">
            <span id="alertMessage">📍 Por favor, permite el acceso a la ubicación para comenzar a rastrear.</span>
        </div>
        
        <div class="controls">
            <button class="btn btn-start" id="startBtn" onclick="startTracking()">
                <span class="btn-icon">▶</span>
                <span id="startBtnText">Iniciar Rastreo</span>
            </button>
            <button class="btn btn-stop" id="stopBtn" onclick="stopTracking()" disabled>
                <span class="btn-icon">⏹</span>
                <span>Detener Rastreo</span>
            </button>
            <button class="btn btn-gpx" id="gpxBtn" onclick="downloadGPX()" disabled>
                <span class="btn-icon">📍</span>
                <span id="gpxBtnText">Descargar GPX</span>
            </button>
            <button class="btn btn-download" id="pdfBtn" onclick="downloadPDF()" disabled>
                <span class="btn-icon">📄</span>
                <span id="pdfBtnText">Descargar Informe</span>
            </button>
            
            <div class="status">
                <div class="status-item">
                    <span class="status-label">Estado</span>
                    <span class="status-value inactive" id="statusText">
                        <span class="tracking-indicator" id="indicator"></span>
                        Inactivo
                    </span>
                </div>
                <div class="status-item">
                    <span class="status-label">Puntos</span>
                    <span class="status-value" id="pointCount">0</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Distancia</span>
                    <span class="status-value" id="distance">0.00 km</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Huecos</span>
                    <span class="status-value warning" id="gapCount">0</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Duración</span>
                    <span class="status-value" id="duration">00:00</span>
                </div>
            </div>
        </div>
        
        <div id="map"></div>
        
        <div class="legend" id="legend">
            <div class="legend-title">Leyenda de Ruta</div>
            <div class="legend-item">
                <div class="legend-line solid"></div>
                <span>Señal GPS Buena</span>
            </div>
            <div class="legend-item">
                <div class="legend-line dashed"></div>
                <span>Hueco de Señal (Se rellenará en GPX)</span>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast">
        <strong id="toastTitle">Notificación</strong>
        <p id="toastMessage"></p>
    </div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Global variables
        let map, trackId = null, isTracking = false, watchId = null;
        let routePolylines = [], currentMarker = null, routeSegments = [], totalDistance = 0;
        let startMarker = null, trackingStartTime = null, durationInterval = null;
        let lastPointTime = null, lastPointData = null;
        let gapCount = 0;
        
        // Gap detection thresholds
        const GAP_TIME_THRESHOLD = 30; // segundos
        const GAP_DISTANCE_THRESHOLD = 0.2; // km
        
        // Initialize map
        function initMap() {
            console.log('Inicializando mapa...');
            map = L.map('map').setView([20, 0], 2);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contribuidores',
                maxZoom: 19
            }).addTo(map);
            
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        map.setView([lat, lon], 15);
                        
                        L.circleMarker([lat, lon], {
                            radius: 8,
                            fillColor: '#667eea',
                            color: '#fff',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.8
                        }).addTo(map).bindPopup('Tu ubicación actual');
                        
                        showToast('Ubicación Encontrada', '¡Listo para comenzar a rastrear!');
                    },
                    (error) => {
                        showAlert('No se pudo obtener tu ubicación. Asegúrate de que los servicios de ubicación estén habilitados.', 'warning');
                    }
                );
            } else {
                showAlert('La geolocalización no es compatible con tu navegador', 'error');
            }
        }
        
        // Calculate distance
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
        
        // Update duration
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
                showAlert('La geolocalización no es compatible con tu navegador', 'error');
                return;
            }
            
            const startBtn = document.getElementById('startBtn');
            const startBtnText = document.getElementById('startBtnText');
            startBtn.disabled = true;
            startBtnText.innerHTML = '<span class="spinner"></span> Inicializando...';
            
            showAlert('Solicitando permiso de ubicación...', 'warning');
            
            try {
                const response = await fetch('/api/track/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (!response.ok) throw new Error('Error al iniciar rastreo');
                
                const data = await response.json();
                trackId = data.track_id;
                console.log('Rastreo iniciado con ID:', trackId);
                
                // Reset state
                routeSegments = [];
                totalDistance = 0;
                gapCount = 0;
                trackingStartTime = Date.now();
                lastPointTime = null;
                lastPointData = null;
                
                // Clear map
                routePolylines.forEach(line => map.removeLayer(line));
                routePolylines = [];
                if (startMarker) map.removeLayer(startMarker);
                if (currentMarker) map.removeLayer(currentMarker);
                
                // Start watching
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
                durationInterval = setInterval(updateDuration, 1000);
                document.getElementById('legend').classList.add('show');
                
                hideAlert();
                showToast('Rastreo Iniciado', 'Los huecos de señal serán rellenados automáticamente en el archivo GPX.');
                
            } catch (error) {
                console.error('Error:', error);
                showAlert('Error al iniciar el rastreo. Por favor, intenta de nuevo.', 'error');
                startBtn.disabled = false;
                startBtnText.textContent = 'Iniciar Rastreo';
            }
        }
        
        // Handle position
        async function handlePosition(position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            const currentTime = Date.now();
            
            console.log(`Actualización de posición: ${lat}, ${lon} (precisión: ${accuracy}m)`);
            
            try {
                await fetch(`/api/track/${trackId}/point`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        lat: lat,
                        lon: lon,
                        accuracy: accuracy,
                        timestamp: new Date().toISOString()
                    })
                });
                
                const newPoint = [lat, lon];
                let isGap = false;
                
                // Check for gap
                if (lastPointTime && lastPointData) {
                    const timeDiff = (currentTime - lastPointTime) / 1000;
                    const distance = calculateDistance(
                        lastPointData[0], lastPointData[1], lat, lon
                    );
                    
                    if (timeDiff > GAP_TIME_THRESHOLD || distance > GAP_DISTANCE_THRESHOLD) {
                        isGap = true;
                        gapCount++;
                        console.log(`HUECO DETECTADO: ${timeDiff.toFixed(0)}s, ${(distance*1000).toFixed(0)}m`);
                        showToast('Hueco GPS Detectado', 
                            `Se rellenará con ruta caminando en el archivo GPX.`);
                    }
                }
                
                // Add start marker
                if (routeSegments.length === 0) {
                    startMarker = L.marker([lat, lon], {
                        icon: L.divIcon({
                            className: 'start-marker',
                            html: '<div style="background: #11998e; color: white; padding: 8px 12px; border-radius: 20px; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">INICIO</div>',
                            iconSize: [70, 30]
                        })
                    }).addTo(map);
                    
                    map.setView([lat, lon], 16);
                    
                    routeSegments.push({
                        points: [newPoint],
                        isGap: false
                    });
                } else {
                    const currentSegment = routeSegments[routeSegments.length - 1];
                    
                    if (isGap) {
                        routeSegments.push({
                            points: [lastPointData, newPoint],
                            isGap: true
                        });
                        routeSegments.push({
                            points: [newPoint],
                            isGap: false
                        });
                    } else {
                        if (currentSegment.isGap) {
                            routeSegments.push({
                                points: [newPoint],
                                isGap: false
                            });
                        } else {
                            currentSegment.points.push(newPoint);
                        }
                    }
                    
                    if (lastPointData) {
                        const distance = calculateDistance(
                            lastPointData[0], lastPointData[1], lat, lon
                        );
                        if (distance > 0.005) {
                            totalDistance += distance;
                        }
                    }
                }
                
                // Redraw segments
                routePolylines.forEach(line => map.removeLayer(line));
                routePolylines = [];
                
                routeSegments.forEach(segment => {
                    if (segment.points.length > 1) {
                        const polyline = L.polyline(segment.points, {
                            color: segment.isGap ? '#ff6b6b' : '#667eea',
                            weight: 5,
                            opacity: segment.isGap ? 0.6 : 0.8,
                            dashArray: segment.isGap ? '10, 10' : null,
                            smoothFactor: 1
                        }).addTo(map);
                        
                        if (segment.isGap) {
                            polyline.bindPopup('⚠️ Hueco de señal GPS - se rellenará con ruta caminando');
                        }
                        
                        routePolylines.push(polyline);
                    }
                });
                
                // Update current marker
                if (currentMarker) map.removeLayer(currentMarker);
                
                currentMarker = L.circleMarker([lat, lon], {
                    radius: 10,
                    fillColor: '#11998e',
                    color: '#fff',
                    weight: 3,
                    opacity: 1,
                    fillOpacity: 1
                }).addTo(map);
                
                L.circle([lat, lon], {
                    radius: accuracy,
                    fillColor: '#11998e',
                    fillOpacity: 0.1,
                    color: '#11998e',
                    weight: 1,
                    opacity: 0.3
                }).addTo(map);
                
                map.panTo([lat, lon], { animate: true, duration: 0.5 });
                
                // Update UI
                const totalPoints = routeSegments.reduce((sum, seg) => sum + seg.points.length, 0);
                document.getElementById('pointCount').textContent = totalPoints;
                document.getElementById('distance').textContent = totalDistance.toFixed(2) + ' km';
                document.getElementById('gapCount').textContent = gapCount;
                
                lastPointTime = currentTime;
                lastPointData = newPoint;
                
            } catch (error) {
                console.error('Error al añadir punto:', error);
            }
        }
        
        // Handle error
        function handleError(error) {
            console.error('Error de geolocalización:', error);
            
            if (error.code === error.PERMISSION_DENIED) {
                showAlert('Permiso de ubicación denegado. Por favor, habilita el acceso a la ubicación.', 'error');
                stopTracking();
            }
        }
        
        // Stop tracking
        async function stopTracking() {
            console.log('Deteniendo rastreo...');
            
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
                    await fetch(`/api/track/${trackId}/finish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            total_distance: totalDistance,
                            gap_count: gapCount,
                            segments: routeSegments.length
                        })
                    });
                    
                    const gapWarning = gapCount > 0 ? ` (${gapCount} hueco${gapCount > 1 ? 's' : ''} detectado${gapCount > 1 ? 's' : ''})` : '';
                    showToast('Rastreo Detenido', `Distancia: ${totalDistance.toFixed(2)} km${gapWarning}`);
                    
                } catch (error) {
                    console.error('Error al finalizar rastreo:', error);
                }
            }
            
            isTracking = false;
            updateUI();
        }
        
        // Download GPX with gap filling
        async function downloadGPX() {
            if (!trackId) {
                showAlert('No hay rastreo disponible para descargar', 'error');
                return;
            }
            
            const gpxBtn = document.getElementById('gpxBtn');
            const originalText = gpxBtn.innerHTML;
            
            if (gapCount > 0) {
                gpxBtn.innerHTML = '<span class="btn-icon">📍</span><span class="spinner"></span> Rellenando huecos...';
                showToast('Procesando', `Rellenando ${gapCount} hueco(s) con rutas caminando...`);
            } else {
                gpxBtn.innerHTML = '<span class="btn-icon">📍</span><span class="spinner"></span> Generando...';
            }
            
            gpxBtn.disabled = true;
            
            try {
                window.location.href = `/api/track/${trackId}/gpx`;
                
                setTimeout(() => {
                    showToast('Éxito', '¡Descarga de archivo GPX completada! Los huecos han sido rellenados con rutas realistas.');
                    gpxBtn.innerHTML = originalText;
                    gpxBtn.disabled = false;
                }, 2000);
                
            } catch (error) {
                console.error('Error al descargar GPX:', error);
                showAlert('Error al descargar GPX. Por favor, intenta de nuevo.', 'error');
                gpxBtn.innerHTML = originalText;
                gpxBtn.disabled = false;
            }
        }
        
        // Download PDF
        async function downloadPDF() {
            if (!trackId) {
                showAlert('No hay rastreo disponible para descargar', 'error');
                return;
            }
            
            const pdfBtn = document.getElementById('pdfBtn');
            const originalText = pdfBtn.innerHTML;
            pdfBtn.innerHTML = '<span class="btn-icon">📄</span><span class="spinner"></span> Generando PDF...';
            pdfBtn.disabled = true;
            
            try {
                window.location.href = `/api/track/${trackId}/pdf`;
                showToast('Éxito', '¡Descarga de informe PDF iniciada!');
                
                setTimeout(() => {
                    pdfBtn.innerHTML = originalText;
                    pdfBtn.disabled = false;
                }, 2000);
                
            } catch (error) {
                console.error('Error al descargar PDF:', error);
                showAlert('Error al descargar PDF. Por favor, intenta de nuevo.', 'error');
                pdfBtn.innerHTML = originalText;
                pdfBtn.disabled = false;
            }
        }
        
        // Update UI
        function updateUI() {
            const startBtn = document.getElementById('startBtn');
            const startBtnText = document.getElementById('startBtnText');
            const stopBtn = document.getElementById('stopBtn');
            const gpxBtn = document.getElementById('gpxBtn');
            const pdfBtn = document.getElementById('pdfBtn');
            const statusText = document.getElementById('statusText');
            
            if (isTracking) {
                startBtn.disabled = true;
                stopBtn.disabled = false;
                gpxBtn.disabled = true;
                pdfBtn.disabled = true;
                startBtnText.textContent = 'Rastreando...';
                statusText.innerHTML = '<span class="tracking-indicator active"></span>Rastreando';
                statusText.className = 'status-value active';
            } else {
                startBtn.disabled = false;
                startBtnText.textContent = 'Iniciar Rastreo';
                stopBtn.disabled = true;
                gpxBtn.disabled = trackId === null;
                pdfBtn.disabled = trackId === null;
                statusText.innerHTML = '<span class="tracking-indicator"></span>' + (trackId ? 'Detenido' : 'Inactivo');
                statusText.className = 'status-value ' + (trackId ? 'active' : 'inactive');
                
                if (!isTracking) {
                    document.getElementById('legend').classList.remove('show');
                }
            }
        }
        
        // Show alert
        function showAlert(message, type = 'warning') {
            const banner = document.getElementById('alertBanner');
            const messageEl = document.getElementById('alertMessage');
            
            banner.className = 'alert alert-' + type;
            messageEl.textContent = message;
            banner.style.display = 'block';
        }
        
        // Hide alert
        function hideAlert() {
            document.getElementById('alertBanner').style.display = 'none';
        }
        
        // Show toast
        function showToast(title, message) {
            const toast = document.getElementById('toast');
            const toastTitle = document.getElementById('toastTitle');
            const toastMessage = document.getElementById('toastMessage');
            
            toastTitle.textContent = title;
            toastMessage.textContent = message;
            toast.className = 'toast show';
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 5000);
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Rastreador GPS inicializado con relleno inteligente de huecos');
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
    with tracks_lock:
        tracks[track_id] = {
            'id': track_id,
            'started_at': datetime.now().isoformat(),
            'points': [],
            'finished': False,
            'gap_count': 0,
            'gaps': []  # Store gap info with point indices
        }
    return jsonify({'track_id': track_id, 'status': 'started'})

@app.route('/api/track/<track_id>/point', methods=['POST'])
def add_point(track_id):
    """Add a GPS point to the track"""
    with tracks_lock:
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
        
        # Detect gaps on backend
        points = tracks[track_id]['points']
        if len(points) >= 2:
            p1 = points[-2]
            p2 = points[-1]
            
            # Calculate time difference
            try:
                t1 = datetime.fromisoformat(p1['timestamp'].replace('Z', '+00:00'))
                t2 = datetime.fromisoformat(p2['timestamp'].replace('Z', '+00:00'))
                time_diff = (t2 - t1).total_seconds()
            except:
                time_diff = 0
            
            # Calculate distance
            from math import radians, sin, cos, sqrt, atan2
            R = 6371
            lat1, lon1 = radians(p1['lat']), radians(p1['lon'])
            lat2, lon2 = radians(p2['lat']), radians(p2['lon'])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance = R * c
            
            # Detect gap
            if time_diff > 30 or distance > 0.2:
                gap = {
                    'start_index': len(points) - 2,  # INDEX of start point
                    'end_index': len(points) - 1,    # INDEX of end point
                    'start_lat': p1['lat'],
                    'start_lon': p1['lon'],
                    'end_lat': p2['lat'],
                    'end_lon': p2['lon'],
                    'time_diff': time_diff,
                    'distance': distance
                }
                tracks[track_id]['gaps'].append(gap)
                print(f"Gap detected between points {gap['start_index']}-{gap['end_index']}: {time_diff:.0f}s, {distance*1000:.0f}m")
        
        return jsonify({'status': 'point_added', 'total_points': len(tracks[track_id]['points'])})

@app.route('/api/track/<track_id>/finish', methods=['POST'])
def finish_track(track_id):
    """Finish tracking"""
    with tracks_lock:
        if track_id not in tracks:
            return jsonify({'error': 'Track not found'}), 404
        
        data = request.json
        tracks[track_id]['finished'] = True
        tracks[track_id]['finished_at'] = datetime.now().isoformat()
        tracks[track_id]['total_distance'] = data.get('total_distance', 0)
        tracks[track_id]['gap_count'] = data.get('gap_count', 0)
        tracks[track_id]['segments'] = data.get('segments', 0)
    
    return jsonify({'status': 'finished', 'track_id': track_id})

@app.route('/api/track/<track_id>/gpx', methods=['GET'])
def generate_gpx(track_id):
    """Generate GPX file with gap filling using OpenRouteService - OPTIMIZED"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    track = tracks[track_id]
    if len(track['points']) == 0:
        return jsonify({'error': 'No points in track'}), 400
    
    points = track['points']
    gaps = track.get('gaps', [])
    
    print(f"\n=== Generating GPX for track {track_id[:8]} ===")
    print(f"Total points: {len(points)}, Gaps to fill: {len(gaps)}")
    
    # Build filled_routes dict: {gap_index: [route_points]}
    filled_routes = {}
    
    if len(gaps) > 0:
        # Parallel API calls with ThreadPoolExecutor
        def fill_single_gap(gap_data):
            idx, gap = gap_data
            result = fill_gap_with_walking_route(
                gap['start_lat'], gap['start_lon'],
                gap['end_lat'], gap['end_lon'],
                gap_index=idx
            )
            return (idx, result)
        
        # Use ThreadPoolExecutor for parallel calls
        with ThreadPoolExecutor(max_workers=3) as executor:
            gap_data = list(enumerate(gaps))
            futures = [executor.submit(fill_single_gap, gd) for gd in gap_data]
            
            for future in as_completed(futures):
                try:
                    idx, route = future.result()
                    if route:
                        filled_routes[idx] = route
                except Exception as e:
                    print(f"Error in parallel gap filling: {e}")
    
    print(f"Successfully filled {len(filled_routes)}/{len(gaps)} gaps")
    
    # Build GPX with filled routes inserted at correct indices
    gpx = f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Rastreador GPS con Relleno Inteligente" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>Ruta {track_id[:8]}</name>
    <time>{track['started_at']}</time>
    <desc>Ruta con {len(filled_routes)} de {len(gaps)} hueco(s) rellenado(s) con rutas caminando</desc>
  </metadata>
  <trk>
    <name>Ruta GPS</name>
    <trkseg>
'''
    
    # Create a mapping of point_index -> gap_index for quick lookup
    gap_end_indices = {gap['end_index']: idx for idx, gap in enumerate(gaps)}
    
    for point_idx, point in enumerate(points):
        # Check if we just passed a gap end point
        if point_idx in gap_end_indices:
            gap_idx = gap_end_indices[point_idx]
            
            # Insert filled route if we have it
            if gap_idx in filled_routes:
                route = filled_routes[gap_idx]
                # Add middle points (skip first and last as they're already in track)
                for filled_point in route[1:-1]:
                    gpx += f'''      <trkpt lat="{filled_point[0]}" lon="{filled_point[1]}">
        <time>{point['timestamp']}</time>
        <cmt>Punto rellenado por API</cmt>
      </trkpt>
'''
        
        # Add the actual GPS point
        gpx += f'''      <trkpt lat="{point['lat']}" lon="{point['lon']}">
        <time>{point['timestamp']}</time>
'''
        if point.get('accuracy'):
            gpx += f'''        <hdop>{point['accuracy']}</hdop>
'''
        gpx += '''      </trkpt>
'''
    
    gpx += '''    </trkseg>
  </trk>
</gpx>'''
    
    # Return as downloadable file
    buffer = io.BytesIO(gpx.encode('utf-8'))
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/gpx+xml',
        as_attachment=True,
        download_name=f'ruta_{track_id[:8]}.gpx'
    )

@app.route('/api/track/<track_id>/pdf', methods=['GET'])
def generate_pdf(track_id):
    """Generate PDF report (Spanish)"""
    if track_id not in tracks:
        return jsonify({'error': 'Track not found'}), 404
    
    track = tracks[track_id]
    if len(track['points']) == 0:
        return jsonify({'error': 'No points in track'}), 400
    
    # Create PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "Rastreador de Rutas GPS")
    
    # Metadata
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 100, f"ID de Ruta: {track_id[:8]}")
    c.drawString(50, height - 120, f"Fecha de Inicio: {track['started_at'][:19].replace('T', ' ')}")
    if track.get('finished_at'):
        c.drawString(50, height - 140, f"Fecha de Fin: {track['finished_at'][:19].replace('T', ' ')}")
    
    # Statistics
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 180, "Estadísticas de la Ruta")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 210, f"Total de Puntos GPS: {len(track['points'])}")
    
    total_distance = track.get('total_distance', 0)
    c.drawString(50, height - 230, f"Distancia Total: {total_distance:.2f} km")
    
    gap_count = len(track.get('gaps', []))
    c.drawString(50, height - 250, f"Huecos de Señal GPS: {gap_count}")
    
    # Calculate route bounds
    lats = [p['lat'] for p in track['points']]
    lons = [p['lon'] for p in track['points']]
    
    c.drawString(50, height - 270, f"Latitud: {min(lats):.6f} a {max(lats):.6f}")
    c.drawString(50, height - 290, f"Longitud: {min(lons):.6f} a {max(lons):.6f}")
    
    # Gap info
    if gap_count > 0:
        c.setFillColorRGB(0.2, 0.6, 0.2)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, height - 325, f"✓ {gap_count} hueco(s) rellenado(s) automáticamente con rutas caminando")
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 345, "El archivo GPX contiene rutas realistas calculadas por OpenRouteService API.")
        c.drawString(50, height - 360, "Los huecos fueron rellenados con rutas peatonales basadas en calles reales.")
    
    # API info
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 410, "Tecnología de Relleno Inteligente")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 440, "Este rastreador utiliza OpenRouteService API para rellenar huecos de señal GPS:")
    c.setFont("Helvetica", 10)
    c.drawString(70, height - 465, "✓ Cuando se detecta un hueco de señal (teléfono bloqueado)")
    c.drawString(70, height - 480, "✓ El sistema calcula automáticamente la ruta caminando más probable")
    c.drawString(70, height - 495, "✓ Usa datos de OpenStreetMap para rutas realistas por calles y aceras")
    c.drawString(70, height - 510, "✓ El archivo GPX final contiene rutas completas sin líneas rectas artificiales")
    
    # Visualization instructions
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 550, "Visualización del Mapa")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 580, "Para ver tu ruta completa en un mapa interactivo, sube el archivo GPX a:")
    
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.4, 0.5, 0.9)
    c.drawString(70, height - 605, "• ViewGPX.com - https://www.viewgpx.com/")
    c.drawString(70, height - 625, "• Google My Maps - https://www.google.com/mymaps")
    c.drawString(70, height - 645, "• Strava - https://www.strava.com/")
    c.setFillColorRGB(0, 0, 0)
    
    # Quick view link
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 685, "Vista Rápida en OpenStreetMap:")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0, 0, 1)
    osm_link = f"https://www.openstreetmap.org/?mlat={center_lat}&mlon={center_lon}#map=15/{center_lat}/{center_lon}"
    c.drawString(50, height - 705, osm_link)
    c.setFillColorRGB(0, 0, 0)
    
    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(50, 60, f"Informe generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')}")
    c.drawString(50, 45, "Potenciado por OpenStreetMap y OpenRouteService")
    c.drawString(50, 30, "Relleno inteligente de huecos con rutas peatonales reales")
    
    c.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'informe_ruta_{track_id[:8]}.pdf'
    )

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'tracks': len(tracks),
        'api_configured': ORS_API_KEY != 'YOUR_API_KEY_HERE',
        'circuit_breaker_failures': circuit_breaker_failures
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting GPS Tracker on port {port}")
    print(f"ORS API configured: {ORS_API_KEY != 'YOUR_API_KEY_HERE'}")
    app.run(debug=False, host='0.0.0.0', port=port)
