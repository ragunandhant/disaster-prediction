import os
import hashlib
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://"
)

# Get OpenWeatherMap API key from environment variable
WEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', 'your_api_key_here')

# Disaster type mapping based on hash prefix
DISASTER_MAPPING = {
    range(0, 32): {"type": "Flood", "confidence_score": 0.87, "risk_level": "High", "recommendations": "Evacuate low areas immediately. Secure valuables on higher ground."},
    range(32, 64): {"type": "Storm", "confidence_score": 0.75, "risk_level": "Medium", "recommendations": "Stay indoors and away from windows. Secure loose outdoor items."},
    range(64, 96): {"type": "Drought", "confidence_score": 0.65, "risk_level": "Medium", "recommendations": "Conserve water. Implement water-saving measures. Monitor local advisories."},
    range(96, 128): {"type": "Earthquake", "confidence_score": 0.45, "risk_level": "Low", "recommendations": "Monitor seismic activity reports. Ensure emergency kits are prepared."},
    range(128, 160): {"type": "Wildfire", "confidence_score": 0.72, "risk_level": "Medium", "recommendations": "Clear dry vegetation around property. Stay updated on evacuation notices."},
    range(160, 192): {"type": "Tornado", "confidence_score": 0.60, "risk_level": "Medium", "recommendations": "Identify safe shelter locations. Keep emergency radio accessible."},
    range(192, 224): {"type": "Heatwave", "confidence_score": 0.80, "risk_level": "High", "recommendations": "Stay hydrated. Limit outdoor activities. Check on vulnerable individuals."},
    range(224, 256): {"type": "None", "confidence_score": 0.01, "risk_level": "Low", "recommendations": "No immediate action required. Continue normal activities."}
}

def get_weather_data(lat, lon):
    """Fetch weather data from OpenWeatherMap API."""
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching weather data: {e}")
        return None

def parse_weather_data(weather_data):
    """Extract relevant parameters from weather API response."""
    if not weather_data:
        return None
    
    try:
        return {
            "temperature": round(weather_data.get("main", {}).get("temp", 0), 1),
            "humidity": weather_data.get("main", {}).get("humidity", 0),
            "wind_speed": weather_data.get("wind", {}).get("speed", 0),
            "pressure": weather_data.get("main", {}).get("pressure", 0),
            "cloud_coverage": weather_data.get("clouds", {}).get("all", 0),
            "description": weather_data.get("weather", [{}])[0].get("description", "unknown")
        }
    except (KeyError, IndexError) as e:
        app.logger.error(f"Error parsing weather data: {e}")
        return None

def generate_prediction_key(weather_params):
    """Create a deterministic key from weather parameters."""
    if not weather_params:
        return None
    
    # Create a string representation of the parameters
    key_string = f"{weather_params['temperature']}_{weather_params['humidity']}_{weather_params['wind_speed']}_{weather_params['pressure']}_{weather_params['cloud_coverage']}_{weather_params['description']}"
    
    # Hash the key string using SHA-256
    hash_object = hashlib.sha256(key_string.encode())
    hex_dig = hash_object.hexdigest()
    
    return hex_dig

def get_disaster_prediction(hash_key):
    """Map the hash key to a deterministic disaster prediction."""
    if not hash_key:
        return {"type": "Error", "confidence_score": 0, "risk_level": "Unknown", "recommendations": "Insufficient data for prediction."}
    
    # Convert first two characters of hash to integer (0-255)
    hash_value = int(hash_key[:2], 16)
    
    # Find the matching disaster type based on the hash value
    for hash_range, prediction in DISASTER_MAPPING.items():
        if hash_value in hash_range:
            return prediction
    
    # Fallback prediction if no range matches (shouldn't happen)
    return {"type": "None", "confidence_score": 0.01, "risk_level": "Low", "recommendations": "No immediate action required."}

@app.route('/predict-disaster', methods=['POST'])
@limiter.limit("60 per minute")
def predict_disaster():
    """Endpoint to predict disasters based on geographical coordinates."""
    # Get request data
    data = request.get_json()
    
    # Validate input
    if not data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({"error": "Missing required parameters: latitude and longitude"}), 400
    
    try:
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
    except ValueError:
        return jsonify({"error": "Invalid coordinates format. Latitude and longitude must be numeric."}), 400
    
    # Validate coordinate ranges
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return jsonify({"error": "Coordinates out of range. Latitude must be between -90 and 90, longitude between -180 and 180."}), 400
    
    # Fetch weather data
    weather_data = get_weather_data(latitude, longitude)
    if not weather_data:
        return jsonify({"error": "Failed to fetch weather data. Please try again later."}), 503
    
    # Parse weather parameters
    weather_params = parse_weather_data(weather_data)
    if not weather_params:
        return jsonify({"error": "Failed to process weather data. Please try again later."}), 500
    
    # Generate prediction key and get disaster prediction
    hash_key = generate_prediction_key(weather_params)
    disaster_prediction = get_disaster_prediction(hash_key)
    
    # Prepare response
    response = {
        "location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "weather_snapshot": weather_params,
        "disaster_prediction": disaster_prediction,
        "disclaimer": "This is a mock prediction for testing purposes only. Not for actual disaster response."
    }
    
    return jsonify(response)

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint for health checking the API."""
    return jsonify({"status": "healthy", "service": "Mock Disaster Prediction API"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))