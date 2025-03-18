import json
import logging
from typing import Optional, List, Dict, Any
from kafka import KafkaConsumer
from prometheus_client import Counter, Gauge, CollectorRegistry
from config import Config

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.consumer: Optional[KafkaConsumer] = None
        self.latest_metrics: List[Dict] = []  # Store latest metrics
        self.registry = registry or CollectorRegistry()
        self.metric_gauges = {}  # Store metric gauges by name
        self.connection_details = ""

        # Service monitoring metrics
        self.metrics_consumed = Counter('kafka_metrics_consumed_total', 
                                     'Total metrics consumed from Kafka',
                                     registry=self.registry)
        self._initialize_consumer()

    def _initialize_consumer(self) -> bool:
        """Initialize the Kafka consumer"""
        try:
            logger.info(f"Attempting to connect consumer to Kafka at {Config.KAFKA_BOOTSTRAP_SERVERS}")
            logger.debug(f"Consumer configuration: topic={Config.KAFKA_TOPIC}, client_id={Config.KAFKA_CLIENT_ID}-consumer")

            self.consumer = KafkaConsumer(
                Config.KAFKA_TOPIC,
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                client_id=f"{Config.KAFKA_CLIENT_ID}-consumer",
                group_id=f"{Config.KAFKA_CLIENT_ID}-metrics-group",
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            self.connection_details = "Connected to Kafka successfully"
            logger.info(self.connection_details)
            return True
        except Exception as e:
            self.connection_details = f"Failed to initialize Kafka consumer: {str(e)}"
            logger.error(self.connection_details, exc_info=True)
            self.consumer = None
            return False

    def _create_or_get_gauge(self, metric_name: str, labels: Optional[Dict[str, str]] = None) -> Gauge:
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

    def get_latest_metrics(self) -> List[Dict[str, Any]]:
        """Retrieve the latest consumed metrics"""
        return self.latest_metrics

    def get_status(self) -> Dict[str, str]:
        """Get detailed consumer status"""
        return {
            "status": "connected" if self.consumer is not None else "disconnected",
            "details": self.connection_details
        }

    def start_consuming(self):
        """Start consuming messages from Kafka"""
        if not self.consumer and not self._initialize_consumer():
            logger.error("Failed to start Kafka consumer")
            return

        try:
            logger.info(f"Starting to consume metrics from topic: {Config.KAFKA_TOPIC}")
            logger.debug("Consumer loop starting - waiting for messages...")

            for message in self.consumer:
                try:
                    logger.debug(f"Received message from partition={message.partition}, offset={message.offset}")
                    metric_data = message.value

                    if not isinstance(metric_data, dict):
                        logger.warning(f"Invalid message format - expected dict, got {type(metric_data)}")
                        continue

                    if 'name' not in metric_data or 'value' not in metric_data:
                        logger.warning(f"Missing required fields in metric data: {metric_data}")
                        continue

                    # Update Prometheus metrics
                    self.metrics_consumed.inc()
                    logger.debug(f"Processing metric: name={metric_data.get('name')}, value={metric_data.get('value')}")

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

                    logger.debug(f"Successfully processed metric: {metric_data['name']} = {metric_data['value']}")
                except Exception as e:
                    logger.error(f"Error processing metric: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error consuming from Kafka: {str(e)}", exc_info=True)
            self.connection_details = f"Consumer error: {str(e)}"
        finally:
            self.close()

    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        return self.consumer is not None

    def close(self):
        """Close the Kafka consumer"""
        if self.consumer:
            self.consumer.close()
            self.consumer = None
            self.latest_metrics = []