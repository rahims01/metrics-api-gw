import logging
from flask import request
from flask_restx import Namespace, Resource, fields
from prometheus_client import Counter, Histogram, Gauge
from services.kafka_producer import KafkaProducerService
from services.kafka_consumer import KafkaConsumerService
from config import Config
import datetime

logger = logging.getLogger(__name__)

metrics_namespace = Namespace('v2', description='API v2 operations')

# Prometheus metrics
metrics_received = Counter('metrics_received_total', 'Total metrics received')
kafka_metrics_sent = Counter('kafka_metrics_sent_total', 'Total metrics sent to Kafka')
kafka_metrics_failed = Counter('kafka_metrics_failed_total', 'Total metrics failed to send to Kafka')
processing_time = Histogram('metrics_processing_seconds', 'Time spent processing metrics')
kafka_connection_status = Gauge('kafka_connection_status', 'Kafka connection status (1=connected, 0=disconnected)')

# Define nested models
metric_payload_model = metrics_namespace.model('MetricPayload', {
    'payload': fields.Raw(required=True, description='Metric payload data'),
    'profileId': fields.String(required=True, description='Profile identifier'),
    'tags': fields.Raw(description='Metric tags'),
    'timestamp': fields.DateTime(required=True, description='Metric timestamp')
})

metric_batch_model = metrics_namespace.model('MetricBatch', {
    'metrics': fields.List(fields.Nested(metric_payload_model), required=True, description='List of metrics')
})

# Response models
metrics_response = metrics_namespace.model('MetricsResponse', {
    'metrics': fields.List(fields.Nested(metric_payload_model)),
    'total_count': fields.Integer(description='Total number of metrics'),
    'consumer_status': fields.String(description='Kafka consumer status')
})

health_response = metrics_namespace.model('HealthResponse', {
    'status': fields.String(required=True, description='Overall service status'),
    'components': fields.Raw(required=True, description='Component statuses'),
    'environment': fields.String(required=True, description='Current environment'),
    'timestamp': fields.DateTime(required=True, description='Health check timestamp')
})

kafka_producer = KafkaProducerService()
kafka_consumer = KafkaConsumerService()

def validate_app_id(app_id: str) -> bool:
    """Validate the app_id against configured value"""
    valid_app_id = Config.APP_ID
    return app_id == valid_app_id

@metrics_namespace.route('/app/<string:app_id>/metrics')
@metrics_namespace.param('app_id', 'Application identifier')
class MetricsResource(Resource):
    @metrics_namespace.expect(metric_batch_model)
    @metrics_namespace.response(202, 'Metrics accepted')
    @metrics_namespace.response(400, 'Invalid request')
    @metrics_namespace.response(401, 'Invalid application ID')
    @metrics_namespace.response(500, 'Internal server error')
    def post(self, app_id):
        """Submit batch metrics data"""
        # Validate app_id
        if not validate_app_id(app_id):
            return {'error': 'Invalid application ID'}, 401

        try:
            with processing_time.time():
                data = request.get_json()

                # Validate batch structure
                if not isinstance(data, dict) or 'metrics' not in data:
                    return {'error': 'Invalid metrics batch format'}, 400

                processed_count = 0
                for metric in data['metrics']:
                    # Validate metric structure
                    if not all(key in metric for key in ['payload', 'profileId', 'timestamp']):
                        continue

                    # Update Prometheus counter
                    metrics_received.inc()

                    # Send to Kafka
                    if kafka_producer.send_metric(metric):
                        kafka_metrics_sent.inc()
                        processed_count += 1
                    else:
                        kafka_metrics_failed.inc()

                # Update Kafka connection status
                kafka_connection_status.set(1.0 if kafka_producer.is_connected() else 0.0)

                return {
                    'status': 'accepted',
                    'message': f'Processed {processed_count} metrics successfully'
                }, 202

        except Exception as e:
            logger.error(f"Error processing metrics batch: {str(e)}", exc_info=True)
            return {
                'error': 'Internal server error',
                'message': 'Failed to process metrics batch'
            }, 500

    @metrics_namespace.marshal_with(metrics_response)
    @metrics_namespace.response(200, 'Success')
    @metrics_namespace.response(401, 'Invalid application ID')
    @metrics_namespace.response(500, 'Internal server error')
    def get(self, app_id):
        """Retrieve consumed metrics"""
        if not validate_app_id(app_id):
            return {'error': 'Invalid application ID'}, 401

        try:
            metrics = kafka_consumer.get_latest_metrics()
            return {
                'metrics': metrics,
                'total_count': len(metrics),
                'consumer_status': 'connected' if kafka_consumer.is_connected() else 'disconnected'
            }, 200
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}", exc_info=True)
            return {'error': 'Internal server error'}, 500

@metrics_namespace.route('/app/<string:app_id>/health')
@metrics_namespace.param('app_id', 'Application identifier')
class HealthResource(Resource):
    @metrics_namespace.marshal_with(health_response)
    @metrics_namespace.response(200, 'Success')
    @metrics_namespace.response(401, 'Invalid application ID')
    def get(self, app_id):
        """Get service health status"""
        if not validate_app_id(app_id):
            return {'error': 'Invalid application ID'}, 401

        kafka_status = kafka_producer.is_connected()
        kafka_consumer_status = kafka_consumer.is_connected()

        metrics_stats = {
            'total_received': metrics_received._value.get(),
            'successfully_sent': kafka_metrics_sent._value.get(),
            'failed_sends': kafka_metrics_failed._value.get()
        }

        return {
            'status': 'healthy',
            'components': {
                'kafka_producer': {
                    'status': 'connected' if kafka_status else 'disconnected',
                    'details': 'Development mode enabled' if Config.ENV == 'development' else 'Ready'
                },
                'kafka_consumer': {
                    'status': 'connected' if kafka_consumer_status else 'disconnected',
                    'details': 'Development mode enabled' if Config.ENV == 'development' else 'Ready'
                },
                'metrics_stats': metrics_stats
            },
            'environment': Config.ENV,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }