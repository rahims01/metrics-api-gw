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

        # Initialize metrics
        self.metrics_consumed = Counter('kafka_metrics_consumed_total', 
                                    'Total metrics consumed from Kafka',
                                    registry=self.registry)

        self.batch_size = Gauge('kafka_batch_size_current',
                             'Current batch size of metrics being processed',
                             registry=self.registry)

        self.consumer_health = Gauge('kafka_consumer_health',
                                  'Consumer health status (1=healthy, 0=unhealthy)',
                                  registry=self.registry)

        self.processing_errors = Counter('kafka_processing_errors_total',
                                     'Total number of processing errors',
                                     registry=self.registry)

        if not self.dev_mode:
            self._initialize_consumer()
        else:
            logger.info("Running in development mode - Kafka consumer disabled")
            self.consumer_health.set(1.0)  # Set as healthy in dev mode

    def store_metrics(self, metrics: List[Dict]):
        """Store metrics and update gauges"""
        self.latest_metrics = metrics
        self.batch_size.set(len(metrics))
        self.metrics_consumed.inc(len(metrics))
        logger.debug(f"Stored {len(metrics)} metrics")

    def get_latest_metrics(self) -> List[Dict]:
        """Retrieve the latest consumed metrics"""
        if self.dev_mode and not self.latest_metrics:
            # Return sample data only if no actual metrics exist
            return [
                {
                    "payload": {"type": "system", "value": 42.0},
                    "profileId": "sample-profile",
                    "timestamp": "2024-03-06T10:00:00Z",
                    "tags": {"host": "desktop-1", "environment": "dev"}
                },
                {
                    "payload": {"type": "memory", "value": 67.5},
                    "profileId": "sample-profile",
                    "timestamp": "2024-03-06T10:00:00Z",
                    "tags": {"host": "desktop-1", "environment": "dev"}
                }
            ]
        return self.latest_metrics

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
            self.consumer_health.set(1.0)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {str(e)}")
            self.consumer = None
            self.consumer_health.set(0.0)
            return False

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