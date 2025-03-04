import logging
import atexit
from flask import Flask, Blueprint, send_from_directory
from flask_restx import Api
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from api.metrics_handler import metrics_namespace, kafka_producer
from config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

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

# Add health check endpoint at root level
@app.route('/health')
def health_check():
    """Global health check endpoint"""
    kafka_status = kafka_producer.is_connected()
    return {
        'status': 'healthy',
        'components': {
            'kafka': 'connected' if kafka_status else 'disconnected'
        }
    }, 200 if kafka_status else 503

# Root path redirects to API documentation
@app.route('/')
def root():
    """Redirect root to API documentation"""
    return """
    <html>
        <head>
            <title>Metrics Collection API</title>
            <link rel="stylesheet" href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css">
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

# Serve swagger-ui assets
@app.route('/swagger-ui/<path:filename>')
def serve_swagger_ui(filename):
    return send_from_directory('templates', filename)

# Log all registered routes
logger.info("Registered routes:")
for rule in app.url_map.iter_rules():
    logger.info(f"Route: {rule.rule} -> {rule.endpoint}")

# Add Prometheus WSGI middleware last to avoid conflicts
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app, 
    {'/prometheus-metrics': make_wsgi_app()}  # Changed from '/metrics' to avoid conflicts
)

# Register cleanup function
@atexit.register
def cleanup():
    """Clean up resources on shutdown"""
    if kafka_producer:
        kafka_producer.close()