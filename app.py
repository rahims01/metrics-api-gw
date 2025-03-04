import logging
import atexit
import datetime
from flask import Flask, Blueprint, send_from_directory
from flask_restx import Api
from flask_cors import CORS
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from api.metrics_handler import metrics_namespace, kafka_producer
from config import Config

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Add ProxyFix middleware for proper header handling behind reverse proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Configure CORS
CORS(app, resources={
    r"/api/*": {"origins": Config.CORS_ORIGINS}
})

# Create Blueprint for API
blueprint = Blueprint('api', __name__, url_prefix='/api')

# Initialize Flask-RestX with the blueprint
api = Api(
    blueprint,
    version='1.0',
    title='Metrics Collection API',
    description='API for collecting metrics from TypeScript clients',
    doc='/swagger-ui',  # This will be accessible at /api/swagger-ui
)

# Add namespaces
api.add_namespace(metrics_namespace)

# Register blueprint with Flask app
app.register_blueprint(blueprint)

# Root path redirects to API documentation
@app.route('/')
def root():
    """Landing page with API documentation links"""
    return """
    <html>
        <head>
            <title>Metrics Collection API</title>
            <link rel="stylesheet" href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css">
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body class="container mt-5">
            <h1>Metrics Collection API</h1>
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
    kafka_status = kafka_producer.is_connected()
    health_data = {
        'status': 'healthy' if kafka_status else 'degraded',
        'components': {
            'kafka': {
                'status': 'connected' if kafka_status else 'disconnected',
                'details': 'Ready for metric collection' if kafka_status else 'Operating in metrics-only mode'
            },
            'api': {
                'status': 'healthy',
                'version': '1.0'
            }
        },
        'timestamp': datetime.datetime.utcnow().isoformat()
    }
    return health_data, 200 if kafka_status else 503

# Serve swagger-ui assets
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

# Add Prometheus WSGI middleware last to avoid conflicts
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app, 
    {'/prometheus-metrics': make_wsgi_app()}
)

# Register cleanup function
@atexit.register
def cleanup():
    """Clean up resources on shutdown"""
    if kafka_producer:
        kafka_producer.close()

if __name__ == '__main__':
    # Log startup configuration
    logger.info(f"Starting application in {Config.ENV} mode")
    logger.info(f"Debug mode: {Config.DEBUG}")
    logger.info(f"Log level: {Config.LOG_LEVEL}")