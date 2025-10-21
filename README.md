# GPS-Route-Tracker-
Purpose: Testing real time tracking to embed in clients third-party apps and more


**#What is it?**
A simple web application to track GPS routes using OpenStreetMap and export them as PDF files.

## Features

- 🗺️ Real-time GPS tracking with OpenStreetMap integration
- 📍 No authentication required - open to anyone
- 📊 Live route visualization with distance calculation
- 📄 PDF export of tracked routes
- 📱 Mobile-friendly responsive design

## Quick Start

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser and navigate to:
```
http://localhost:5000
```

### How to Use

1. Click **"Start Tracking"** - the browser will request location permissions
2. Allow location access when prompted
3. Your route will be displayed in real-time on the map
4. Click **"Finish"** when you're done tracking
5. Click **"Download PDF"** to export your route

## Deployment Options

### Option 1: Railway (Recommended for MVP)

Railway offers free tier and is very simple to deploy:

1. Create account at https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub repository
4. Railway will auto-detect Flask and deploy
5. Get your public URL

**Pros**: Free tier, automatic HTTPS, easy setup
**Cons**: Cold starts after inactivity

### Option 2: Render

1. Create account at https://render.com
2. Click "New" → "Web Service"
3. Connect your repository
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`

**Pros**: Free tier, automatic HTTPS, good performance
**Cons**: Limited to 750 hours/month on free tier

### Option 3: Heroku

1. Install Heroku CLI
2. Create a `Procfile`:
```
web: gunicorn app:app
```
3. Deploy:
```bash
heroku create your-app-name
git push heroku main
```

**Pros**: Well-documented, reliable
**Cons**: No free tier (starts at $5/month)

### Option 4: PythonAnywhere

1. Create account at https://www.pythonanywhere.com
2. Upload your files via web interface
3. Configure web app in dashboard
4. Set up WSGI configuration

**Pros**: Free tier available, simple for Python apps
**Cons**: Manual configuration, limited free resources

### Option 5: Local Network (Testing)

For quick local testing accessible on your network:

```bash
python app.py
```

Then access from any device on your network using your computer's IP address:
```
http://YOUR_LOCAL_IP:5000
```

To find your local IP:
- **macOS/Linux**: `ifconfig` or `ip addr`
- **Windows**: `ipconfig`

## Production Deployment with Gunicorn

For production deployment, use Gunicorn instead of Flask's development server:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Important Notes

### HTTPS Requirement

Modern browsers require HTTPS for geolocation API to work (except on localhost). All recommended deployment platforms provide automatic HTTPS.

### Browser Compatibility

The app uses:
- Geolocation API (supported in all modern browsers)
- Leaflet.js for OpenStreetMap
- Standard JavaScript (ES6+)

### Storage

Currently, tracks are stored in memory. For production, consider:
- Using a database (PostgreSQL, MongoDB)
- Implementing track cleanup/expiration
- Adding user sessions or track IDs for retrieval

### PDF Generation

The current PDF includes:
- Track metadata (ID, start time, point count)
- Coordinate list (first 10 points)
- Route statistics

For enhanced PDFs, consider:
- Embedding static map images
- Adding elevation data
- Including speed/pace statistics

## Environment Variables

For production, you may want to set:

```bash
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
```

## Security Considerations

This MVP has no authentication. For production:
- Add user authentication
- Implement rate limiting
- Add CORS restrictions
- Validate all inputs
- Add track ownership/privacy controls

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Mapping**: Leaflet.js + OpenStreetMap
- **PDF**: ReportLab
- **Server**: Gunicorn (production)

## License

MIT License - feel free to modify and use for your purposes.

## Support

For issues or questions about deployment, refer to the respective platform's documentation:
- Railway: https://docs.railway.app
- Render: https://render.com/docs
- Heroku: https://devcenter.heroku.com
- PythonAnywhere: https://help.pythonanywhere.com
