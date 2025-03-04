import json
import logging
import time
from typing import Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError
from config import Config

logger = logging.getLogger(__name__)

class KafkaProducerService:
    def __init__(self):
        self.producer: Optional[KafkaProducer] = None
        self.last_connection_attempt = 0
        self.connection_retry_interval = 5  # seconds
        self._initialize_producer()

    def _initialize_producer(self) -> bool:
        """
        Initialize the Kafka producer with retry mechanism
        Returns True if successfully connected, False otherwise
        """
        current_time = time.time()
        if (current_time - self.last_connection_attempt) < self.connection_retry_interval:
            return False

        self.last_connection_attempt = current_time
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                client_id=Config.KAFKA_CLIENT_ID,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1,
                reconnect_backoff_ms=1000,
                reconnect_backoff_max_ms=10000
            )
            logger.info("Successfully connected to Kafka")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Kafka: {str(e)}")
            self.producer = None
            return False

    def send_metric(self, metric_data):
        """
        Send metric data to Kafka topic
        Returns True if sent successfully, False otherwise
        """
        if not self.producer and not self._initialize_producer():
            logger.warning("Kafka producer not available, storing metrics in Prometheus only")
            return False

        try:
            future = self.producer.send(
                Config.KAFKA_TOPIC,
                value=metric_data
            )
            # Wait for the message to be delivered
            future.get(timeout=2)
            logger.debug(f"Successfully sent metric to Kafka: {metric_data}")
            return True
        except KafkaError as e:
            logger.error(f"Error sending metric to Kafka: {str(e)}")
            self.producer = None  # Reset producer to trigger reconnection
            return False

    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        return self.producer is not None and self._initialize_producer()

    def close(self):
        """Close the Kafka producer"""
        if self.producer:
            self.producer.close()
            self.producer = None