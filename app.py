import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_restx import Api
from api.metrics_handler import metrics_namespace
from config import Config

# Configure logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application initialization...")

        # Initialize Flask app
        app = Flask(__name__)
        app.secret_key = os.environ.get("SESSION_SECRET")

        # Enable CORS
        CORS(app)
        logger.info("CORS enabled")

        # Register API routes
        api = Api(
            title='Metrics Collection API',
            version='2.0',
            description='API for collecting and exposing metrics from TypeScript clients',
            doc='/swagger-ui',
            prefix='/api'
        )
        api.add_namespace(metrics_namespace, path='/v2')
        api.init_app(app)
        logger.info("API routes registered")

        # Simple test endpoint
        @app.route('/ping')
        def ping():
            return jsonify({'status': 'ok', 'message': 'Server is running'}), 200

        logger.info("Test endpoint registered")

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    logger.info(f"Starting application in {Config.ENV} mode")
    app.run(host='0.0.0.0', port=5000, debug=True)