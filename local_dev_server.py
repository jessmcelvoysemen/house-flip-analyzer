#!/usr/bin/env python3
"""
Simple local development server for testing the House Flip Analyzer
Run this instead of Azure Functions Core Tools for quick local testing
"""
import sys
import os
import json
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Load local.settings.json and set environment variables
settings_path = os.path.join(os.path.dirname(__file__), 'local.settings.json')
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
        for key, value in settings.get('Values', {}).items():
            os.environ[key] = str(value)
    print("✅ Loaded local.settings.json")

# Add api directory to path so we can import function_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

# Import the actual Azure Functions logic
from function_app import analyze_neighborhoods, health_check, listings_endpoint

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for local development

# Mock Azure Functions HttpRequest for local dev
class MockRequest:
    def __init__(self, flask_request):
        self.method = flask_request.method
        self.params = flask_request.args
        self.url = flask_request.url

@app.route('/')
def serve_index():
    """Serve the main index.html"""
    return send_from_directory('.', 'index.html')

@app.route('/api/analyze', methods=['GET', 'POST', 'OPTIONS'])
def api_analyze():
    """Proxy to the analyze_neighborhoods function"""
    try:
        mock_req = MockRequest(request)
        response = analyze_neighborhoods(mock_req)
        return response.get_body().decode('utf-8'), response.status_code, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def api_health():
    """Proxy to the health_check function"""
    try:
        mock_req = MockRequest(request)
        response = health_check(mock_req)
        return response.get_body().decode('utf-8'), response.status_code, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/listings', methods=['GET'])
def api_listings():
    """Proxy to the listings_endpoint function"""
    try:
        mock_req = MockRequest(request)
        response = listings_endpoint(mock_req)
        return response.get_body().decode('utf-8'), response.status_code, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🏠 FAMILY FLIP FINDER - Local Development Server")
    print("="*70)
    print(f"\n✅ Server starting at: http://localhost:5001")
    print(f"✅ Open this URL in your browser to test the app")
    print(f"\n📋 API Endpoints:")
    print(f"   - http://localhost:5001/api/analyze")
    print(f"   - http://localhost:5001/api/health")
    print(f"   - http://localhost:5001/api/listings")
    print(f"\n⚠️  Make sure you have your API keys set in local.settings.json")
    print(f"   - RAPIDAPI_KEY (for real estate data)")
    print(f"\n🛑 Press Ctrl+C to stop the server")
    print("="*70 + "\n")

    app.run(host='0.0.0.0', port=5001, debug=True)
