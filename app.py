import os
import atexit
import logging
import threading
from flask import Flask, request
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

# Configure max request size (100MB)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Initialize services with the consumer registry
kafka_producer = KafkaProducerService()
kafka_consumer = KafkaConsumerService(registry=consumer_registry)

# Start Kafka consumer in a background thread
def start_consumer_thread():
    """Start the Kafka consumer in a separate thread"""
    consumer_thread = threading.Thread(target=kafka_consumer.start_consuming, daemon=True)
    consumer_thread.start()
    logger.info("Started Kafka consumer thread")

# Register API routes
from flask_restx import Api
api = Api(
    title='Metrics Collection API',
    version='2.0',
    description='API for collecting and exposing metrics from TypeScript clients',
    doc='/swagger-ui',
    prefix='/api'
)
api.add_namespace(metrics_namespace, path='/v2')
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
                    <li class="list-group-item"><a href="/swagger-ui">API Documentation</a></li>
                    <li class="list-group-item"><a href="/api/v2/app/default-app-id/health">Health Check</a></li>
                    <li class="list-group-item"><a href="/prometheus-metrics">Prometheus Metrics</a></li>
                </ul>
            </div>
        </body>
    </html>
    """

# Add Prometheus WSGI middleware
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
    logger.info(f"Starting application in {Config.ENV} mode")
    logger.info(f"Debug mode: {Config.DEBUG}")
    start_consumer_thread()  # Start consumer before running the app
    app.run(host='0.0.0.0', port=5000, debug=True)