import logging
from flask import request
from flask_restx import Namespace, Resource, fields
from prometheus_client import Counter, Histogram, Gauge
from services.kafka_producer import KafkaProducerService

logger = logging.getLogger(__name__)

metrics_namespace = Namespace('metrics', description='Metrics operations')

# Prometheus metrics
metrics_received = Counter('metrics_received_total', 'Total metrics received')
kafka_metrics_sent = Counter('kafka_metrics_sent_total', 'Total metrics sent to Kafka')
kafka_metrics_failed = Counter('kafka_metrics_failed_total', 'Total metrics failed to send to Kafka')
processing_time = Histogram('metrics_processing_seconds', 'Time spent processing metrics')
kafka_connection_status = Gauge('kafka_connection_status', 'Kafka connection status (1=connected, 0=disconnected)')

# Request model
metric_model = metrics_namespace.model('Metric', {
    'name': fields.String(required=True, description='Metric name'),
    'value': fields.Float(required=True, description='Metric value'),
    'timestamp': fields.DateTime(required=True, description='Metric timestamp'),
    'tags': fields.Raw(description='Additional tags')
})

kafka_producer = KafkaProducerService()

@metrics_namespace.route('')
class MetricsResource(Resource):
    @metrics_namespace.expect(metric_model)
    @metrics_namespace.response(202, 'Metric accepted')
    @metrics_namespace.response(400, 'Invalid request')
    @metrics_namespace.response(500, 'Internal server error')
    def post(self):
        """Submit metrics data"""
        try:
            with processing_time.time():
                data = request.get_json()

                # Validate required fields
                if not all(key in data for key in ['name', 'value', 'timestamp']):
                    return {'error': 'Missing required fields'}, 400

                # Update Prometheus counter for received metrics
                metrics_received.inc()

                # Try to send to Kafka
                if kafka_producer.send_metric(data):
                    kafka_metrics_sent.inc()
                else:
                    kafka_metrics_failed.inc()

                # Update Kafka connection status
                kafka_connection_status.set(1.0 if kafka_producer.is_connected() else 0.0)

                return {'status': 'accepted'}, 202

        except Exception as e:
            logger.error(f"Error processing metric: {str(e)}")
            return {'error': 'Internal server error'}, 500

@metrics_namespace.route('/health')
class HealthResource(Resource):
    @metrics_namespace.doc('get_health_status')
    def get(self):
        """Get metrics service health status"""
        kafka_status = kafka_producer.is_connected()
        kafka_connection_status.set(1.0 if kafka_status else 0.0)

        return {
            'status': 'healthy',
            'kafka_connected': kafka_status
        }