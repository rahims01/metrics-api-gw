import os
import atexit
import datetime
import logging
from typing import Optional

from flask import Flask, send_from_directory
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Counter, Gauge, CollectorRegistry

from config import Config
from services.kafka_producer import KafkaProducerService
from services.kafka_consumer import KafkaConsumerService
from api.metrics_handler import metrics_namespace

# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create a separate registry for consumer metrics
consumer_registry = CollectorRegistry()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize services with the consumer registry
kafka_producer = KafkaProducerService()
kafka_consumer = KafkaConsumerService(registry=consumer_registry)

# Register API routes
from flask_restx import Api
api = Api(
    title='Metrics Collection API',
    version='2.0',
    description='API for collecting and exposing metrics from TypeScript clients',
    doc='/swagger-ui'
)
api.add_namespace(metrics_namespace, path='/api/v2')
api.init_app(app)

# Root endpoint
@app.route('/')
def index():
    """Landing page with API documentation links"""
    return """
    <html>
        <head>
            <title>Metrics Collection API</title>
            <link rel="stylesheet" href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css">
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body class="container mt-5">
            <h1>Metrics Collection API v2.0</h1>
            <div class="mt-4">
                <h2>Available Endpoints:</h2>
                <ul class="list-group">
                    <li class="list-group-item"><a href="/api/swagger-ui">API Documentation (Swagger UI)</a></li>
                    <li class="list-group-item"><a href="/health">Health Check</a></li>
                    <li class="list-group-item"><a href="/prometheus-metrics">Prometheus Metrics</a></li>
                </ul>
            </div>
        </body>
    </html>
    """

# Health check endpoint
@app.route('/health')
def health_check():
    """Global health check endpoint with detailed component status"""
    # In dev mode, both services report as connected
    kafka_producer_status = kafka_producer.is_connected()
    kafka_consumer_status = kafka_consumer.is_connected()

    health_data = {
        'status': 'healthy',  # In dev mode, always healthy
        'components': {
            'kafka_producer': {
                'status': 'connected' if kafka_producer_status else 'disconnected',
                'details': 'Development mode enabled' if Config.ENV == 'development' else 'Ready for metric collection'
            },
            'kafka_consumer': {
                'status': 'connected' if kafka_consumer_status else 'disconnected',
                'details': 'Development mode enabled' if Config.ENV == 'development' else 'Processing metrics'
            },
            'api': {
                'status': 'healthy',
                'version': '2.0'
            }
        },
        'environment': Config.ENV,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }
    return health_data, 200

# Serve swagger UI and static files
@app.route('/api/swagger.json')
def serve_swagger_json():
    return send_from_directory('static', 'swagger.json')

@app.route('/swagger-ui/<path:filename>')
def serve_swagger_ui(filename):
    return send_from_directory('templates', filename)

# Add security headers middleware
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Add error handlers
@app.errorhandler(404)
def not_found_error(error):
    return {'error': 'Not Found', 'message': str(error)}, 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return {'error': 'Internal Server Error', 'message': 'An unexpected error occurred'}, 500

# Log all registered routes
logger.info("Registered routes:")
for rule in app.url_map.iter_rules():
    logger.info(f"Route: {rule.rule} -> {rule.endpoint}")

# Add Prometheus WSGI middleware to expose only consumer metrics
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app, 
    {'/prometheus-metrics': make_wsgi_app(registry=consumer_registry)}
)

# Register cleanup function
@atexit.register
def cleanup():
    """Clean up resources on shutdown"""
    if kafka_producer:
        kafka_producer.close()
    if kafka_consumer:
        kafka_consumer.close()

if __name__ == '__main__':
    # Log startup configuration
    logger.info(f"Starting application in {Config.ENV} mode")
    logger.info(f"Debug mode: {Config.DEBUG}")
    logger.info(f"Log level: {Config.LOG_LEVEL}")