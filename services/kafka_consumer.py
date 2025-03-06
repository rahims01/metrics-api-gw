import json
import logging
from typing import Optional, List, Dict
from kafka import KafkaConsumer
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry
from config import Config

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.consumer: Optional[KafkaConsumer] = None
        self.dev_mode = Config.ENV == 'development'
        self.latest_metrics: List[Dict] = []  # Store latest metrics
        self.registry = registry or CollectorRegistry()
        self.metric_gauges = {}  # Store metric gauges by name

        # Service monitoring metrics
        self.metrics_consumed = Counter('kafka_metrics_consumed_total', 
                                      'Total metrics consumed from Kafka',
                                      registry=self.registry)

        if not self.dev_mode:
            self._initialize_consumer()
        else:
            logger.info("Running in development mode - Kafka consumer disabled")

    def _initialize_consumer(self) -> bool:
        """Initialize the Kafka consumer"""
        try:
            self.consumer = KafkaConsumer(
                Config.KAFKA_TOPIC,
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                client_id=f"{Config.KAFKA_CLIENT_ID}-consumer",
                group_id=f"{Config.KAFKA_CLIENT_ID}-metrics-group",
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            logger.info("Successfully connected Kafka consumer")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {str(e)}")
            self.consumer = None
            return False

    def _create_or_get_gauge(self, metric_name: str, labels: Dict[str, str] = None) -> Gauge:
        """Create or get a Gauge for a metric"""
        gauge_name = f"client_metric_{metric_name}"
        if gauge_name not in self.metric_gauges:
            label_names = list(labels.keys()) if labels else []
            self.metric_gauges[gauge_name] = Gauge(
                gauge_name,
                f'Client metric: {metric_name}',
                labelnames=label_names,
                registry=self.registry
            )
        return self.metric_gauges[gauge_name]

    def get_latest_metrics(self) -> List[Dict]:
        """Retrieve the latest consumed metrics"""
        if self.dev_mode:
            # Return sample data in dev mode
            sample_metrics = [
                {
                    "name": "cpu_usage",
                    "value": 42.0,
                    "timestamp": "2024-03-06T10:00:00Z",
                    "tags": {"host": "desktop-1", "environment": "dev"}
                },
                {
                    "name": "memory_usage",
                    "value": 67.5,
                    "timestamp": "2024-03-06T10:00:00Z",
                    "tags": {"host": "desktop-1", "environment": "dev"}
                }
            ]
            # Update Prometheus metrics in dev mode
            for metric in sample_metrics:
                gauge = self._create_or_get_gauge(metric['name'], metric.get('tags', {}))
                if metric.get('tags'):
                    gauge.labels(**metric['tags']).set(metric['value'])
                else:
                    gauge.set(metric['value'])
            return sample_metrics
        return self.latest_metrics

    def start_consuming(self):
        """Start consuming messages from Kafka"""
        if self.dev_mode:
            logger.info("Development mode: Kafka consumer not started")
            return

        if not self.consumer and not self._initialize_consumer():
            logger.error("Failed to start Kafka consumer")
            return

        try:
            logger.info("Starting to consume metrics from Kafka")
            for message in self.consumer:
                try:
                    metric_data = message.value
                    if isinstance(metric_data, dict) and 'name' in metric_data and 'value' in metric_data:
                        # Update Prometheus metrics
                        self.metrics_consumed.inc()

                        # Create or get Gauge for this metric
                        gauge = self._create_or_get_gauge(
                            metric_data['name'], 
                            metric_data.get('tags', {})
                        )

                        # Set Gauge value with labels if present
                        if metric_data.get('tags'):
                            gauge.labels(**metric_data['tags']).set(float(metric_data['value']))
                        else:
                            gauge.set(float(metric_data['value']))

                        # Store the metric
                        self.latest_metrics.append(metric_data)
                        # Keep only the last 100 metrics
                        if len(self.latest_metrics) > 100:
                            self.latest_metrics.pop(0)

                        logger.debug(f"Processed metric: {metric_data['name']} = {metric_data['value']}")
                except Exception as e:
                    logger.error(f"Error processing metric: {str(e)}")

        except Exception as e:
            logger.error(f"Error consuming from Kafka: {str(e)}")
        finally:
            self.close()

    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        if self.dev_mode:
            return True
        return self.consumer is not None

    def close(self):
        """Close the Kafka consumer"""
        if self.consumer:
            self.consumer.close()
            self.consumer = None
            self.latest_metrics = []