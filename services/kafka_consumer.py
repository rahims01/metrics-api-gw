import json
import logging
from typing import Optional, List, Dict, Any
from confluent_kafka import Consumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from prometheus_client import Counter, Gauge, CollectorRegistry
from config import Config

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.consumer: Optional[Consumer] = None
        self.schema_registry_client: Optional[SchemaRegistryClient] = None
        self.deserializer: Optional[AvroDeserializer] = None
        self.latest_metrics: List[Dict] = []
        self.registry = registry or CollectorRegistry()
        self.metric_gauges = {}
        self.connection_details = ""

        # Service monitoring metrics
        self.metrics_consumed = Counter('kafka_metrics_consumed_total', 
                                    'Total metrics consumed from Kafka',
                                    registry=self.registry)
        self._initialize_consumer()

    def _initialize_consumer(self) -> bool:
        """Initialize the Confluent Kafka consumer with Avro deserialization"""
        try:
            logger.info(f"Attempting to connect consumer to Kafka at {Config.KAFKA_BOOTSTRAP_SERVERS}")

            # Initialize Schema Registry client
            schema_registry_conf = {'url': Config.SCHEMA_REGISTRY_URL}
            self.schema_registry_client = SchemaRegistryClient(schema_registry_conf)

            # Load Avro schema
            with open('schemas/metric.avsc', 'r') as f:
                schema_str = f.read()
                

            # Create Avro deserializer
            self.deserializer = AvroDeserializer(
                schema_registry_client=self.schema_registry_client,
                schema_str=schema_str,
                from_dict=lambda x, ctx: x
            )

            # Configure Kafka Consumer
            consumer_conf = {
                'bootstrap.servers': Config.KAFKA_BOOTSTRAP_SERVERS,
                'group.id': f"{Config.KAFKA_CLIENT_ID}-metrics-group",
                'client.id': f"{Config.KAFKA_CLIENT_ID}-consumer",
                'auto.offset.reset': 'latest',
                'enable.auto.commit': True,
                'security.protocol': Config.KAFKA_SECURITY_PROTOCOL,
                'sasl.mechanisms': Config.KAFKA_SASL_MECHANISM,
                'sasl.kerberos.service.name': Config.KAFKA_SERVICE_NAME,
                'broker.version.fallback': '0.10.1',
                'api.version.request': True
            }

            self.consumer = Consumer(consumer_conf)
            self.consumer.subscribe([Config.KAFKA_TOPIC])

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

    def start_consuming(self):
        """Start consuming messages from Kafka"""
        if not self.consumer and not self._initialize_consumer():
            logger.error("Failed to start Kafka consumer")
            return

        try:
            logger.info(f"Starting to consume metrics from topic: {Config.KAFKA_TOPIC}")

            while True:
                try:
                    msg = self.consumer.poll(1.0)

                    if msg is None:
                        continue
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            continue
                        else:
                            logger.error(f"Consumer error: {msg.error()}")
                            continue

                    # Deserialize the message value using Avro
                    metric_data = self.deserializer(msg.value())

                    logger.debug(f"Received message from partition={msg.partition()}, offset={msg.offset()}")

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

    def get_latest_metrics(self) -> List[Dict[str, Any]]:
        """Retrieve the latest consumed metrics"""
        return self.latest_metrics

    def get_status(self) -> Dict[str, str]:
        """Get detailed consumer status"""
        return {
            "status": "connected" if self.consumer is not None else "disconnected",
            "details": self.connection_details
        }

    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        return self.consumer is not None

    def close(self):
        """Close the Kafka consumer"""
        if self.consumer:
            self.consumer.close()
            self.consumer = None
            self.latest_metrics = []