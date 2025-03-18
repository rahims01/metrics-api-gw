import json
import logging
import time
from typing import Optional, Dict, Any
from confluent_kafka import Producer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from config import Config

logger = logging.getLogger(__name__)

class KafkaProducerService:
    def __init__(self):
        self.producer: Optional[Producer] = None
        self.schema_registry_client: Optional[SchemaRegistryClient] = None
        self.serializer: Optional[AvroSerializer] = None
        self.last_connection_attempt = 0
        self.connection_retry_interval = 5  # seconds
        self.connection_details = ""
        self._initialize_producer()

    def _initialize_producer(self) -> bool:
        """
        Initialize the Confluent Kafka producer with retry mechanism
        Returns True if successfully connected, False otherwise
        """
        current_time = time.time()
        if (current_time - self.last_connection_attempt) < self.connection_retry_interval:
            return False

        self.last_connection_attempt = current_time
        try:
            logger.info(f"Attempting to connect to Kafka at {Config.KAFKA_BOOTSTRAP_SERVERS}")

            # Initialize Schema Registry client
            schema_registry_conf = {'url': Config.SCHEMA_REGISTRY_URL}
            self.schema_registry_client = SchemaRegistryClient(schema_registry_conf)

            # Load and register Avro schema
            with open('schemas/metric.avsc', 'r') as f:
                schema_str = f.read()

            # Create Avro serializer
            self.serializer = AvroSerializer(
                schema_registry_client=self.schema_registry_client,
                schema_str=schema_str,
                to_dict=lambda x, ctx: x
            )

            # Configure Kafka Producer
            producer_conf = {
                'bootstrap.servers': Config.KAFKA_BOOTSTRAP_SERVERS,
                'client.id': Config.KAFKA_CLIENT_ID,
                'security.protocol': Config.KAFKA_SECURITY_PROTOCOL,
                'sasl.mechanisms': Config.KAFKA_SASL_MECHANISM,
                'sasl.kerberos.service.name': Config.KAFKA_SERVICE_NAME,
                'broker.version.fallback': '0.10.1',
                'api.version.request': True,
                'acks': 'all',
                'retries': 3,
                'max.in.flight': 1
            }

            self.producer = Producer(producer_conf)
            self.connection_details = "Connected to Kafka successfully"
            logger.info(self.connection_details)
            return True

        except Exception as e:
            self.connection_details = f"Failed to connect to Kafka: {str(e)}"
            logger.error(self.connection_details, exc_info=True)
            self.producer = None
            return False

    def send_metric(self, metric_data: Dict[str, Any]) -> bool:
        """
        Send metric data to Kafka topic using Avro serialization
        Returns True if sent successfully, False otherwise
        """
        if not self.producer:
            if not self._initialize_producer():
                logger.error(f"Kafka producer not available: {self.connection_details}")
                return False

        try:
            # Serialize the metric data using Avro
            serialized_data = self.serializer(metric_data)

            def delivery_report(err, msg):
                if err is not None:
                    logger.error(f'Message delivery failed: {err}')
                else:
                    logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')

            # Produce message
            self.producer.produce(
                topic=Config.KAFKA_TOPIC,
                value=serialized_data,
                on_delivery=delivery_report
            )

            # Wait for message to be delivered
            self.producer.poll(0)
            self.producer.flush()

            logger.debug(f"Sent metric to Kafka topic={Config.KAFKA_TOPIC}")
            return True

        except Exception as e:
            logger.error(f"Error sending metric to Kafka: {str(e)}", exc_info=True)
            return False

    def get_status(self) -> Dict[str, str]:
        """Get detailed producer status"""
        return {
            "status": "connected" if self.producer is not None else "disconnected",
            "details": self.connection_details
        }

    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        return self.producer is not None

    def close(self):
        """Close the Kafka producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            self.producer = None