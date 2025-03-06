import logging
from flask import request
from flask_restx import Namespace, Resource, fields
from config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

metrics_namespace = Namespace('v2', description='API v2 operations')

# Define nested models
metric_payload_model = metrics_namespace.model('MetricPayload', {
    'payload': fields.Raw(required=True, description='Metric payload data'),
    'profileId': fields.String(required=True, description='Profile identifier'),
    'timestamp': fields.DateTime(required=True, description='Metric timestamp')
})

metric_batch_model = metrics_namespace.model('MetricBatch', {
    'metrics': fields.List(fields.Nested(metric_payload_model), required=True)
})

# Simple test endpoint
@metrics_namespace.route('/test')
class TestResource(Resource):
    def get(self):
        """Test endpoint to verify API is running"""
        return {'status': 'ok', 'message': 'API is running'}, 200

def validate_app_id(app_id: str) -> bool:
    """Validate the app_id against configured value"""
    return app_id == Config.APP_ID

@metrics_namespace.route('/app/<string:app_id>/metrics')
@metrics_namespace.param('app_id', 'Application identifier')
class MetricsResource(Resource):
    @metrics_namespace.expect(metric_batch_model)
    @metrics_namespace.response(202, 'Metrics accepted')
    def post(self, app_id):
        """Submit metrics data"""
        try:
            if not validate_app_id(app_id):
                return {'error': 'Invalid application ID'}, 401

            data = request.get_json()
            logger.debug(f"Received metrics data: {data}")

            return {'status': 'accepted'}, 202

        except Exception as e:
            logger.error(f"Error processing metrics: {str(e)}", exc_info=True)
            return {'error': 'Internal server error'}, 500

    @metrics_namespace.response(200, 'Success')
    def get(self, app_id):
        """Retrieve metrics data"""
        try:
            if not validate_app_id(app_id):
                return {'error': 'Invalid application ID'}, 401

            return {
                'metrics': [],
                'total_count': 0,
                'status': 'ok'
            }, 200

        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}", exc_info=True)
            return {'error': 'Internal server error'}, 500