from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
from datetime import datetime
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import requests
from PIL import Image
import uuid
import os

app = Flask(__name__)
CORS(app)

# Store tracks in memory (for MVP - in production, use a database)
tracks = {}

@app.route('/')
def index():
    return render_template('index.html')

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
    
    # Create PDF
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
    
    # Calculate zoom level based on bounds
    lat_diff = max_lat - min_lat
    lon_diff = max_lon - min_lon
    max_diff = max(lat_diff, lon_diff)
    
    if max_diff < 0.01:
        zoom = 15
    elif max_diff < 0.05:
        zoom = 13
    elif max_diff < 0.1:
        zoom = 12
    elif max_diff < 0.5:
        zoom = 10
    else:
        zoom = 8
    
    c.drawString(50, height - 140, f"Center: {center_lat:.6f}, {center_lon:.6f}")
    c.drawString(50, height - 160, f"Zoom Level: {zoom}")
    
    # Get static map from OpenStreetMap using StaticMap service
    try:
        # Create a path parameter for the route
        path_points = '|'.join([f"{p['lat']},{p['lon']}" for p in track['points']])
        
        # Use a static map service (we'll use staticmap.openstreetmap.de as alternative)
        map_width = 500
        map_height = 400
        
        # For simplicity in MVP, we'll just add route coordinates as text
        # In production, you'd want to use a proper static map API or render the map
        c.drawString(50, height - 200, "Route Coordinates:")
        
        y_pos = height - 220
        for i, point in enumerate(track['points'][:10]):  # Show first 10 points
            c.setFont("Helvetica", 9)
            c.drawString(60, y_pos, f"{i+1}. Lat: {point['lat']:.6f}, Lon: {point['lon']:.6f}")
            y_pos -= 15
            if y_pos < 100:
                break
        
        if len(track['points']) > 10:
            c.drawString(60, y_pos - 10, f"... and {len(track['points']) - 10} more points")
        
    except Exception as e:
        c.drawString(50, height - 200, f"Error generating map: {str(e)}")
    
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
