import json
import logging
import time
import os
from typing import Optional, Dict, Any
from kafka import KafkaProducer
from kafka.errors import KafkaError
from config import Config

logger = logging.getLogger(__name__)

class KafkaProducerService:
    def __init__(self):
        self.producer: Optional[KafkaProducer] = None
        self.last_connection_attempt = 0
        self.connection_retry_interval = 5  # seconds
        self.connection_details = ""
        self._initialize_producer()

    def _initialize_producer(self) -> bool:
        """
        Initialize the Kafka producer with retry mechanism
        Returns True if successfully connected, False otherwise
        """
        # Don't retry too frequently
        current_time = time.time()
        if (current_time - self.last_connection_attempt) < self.connection_retry_interval:
            return False

        self.last_connection_attempt = current_time
        try:
            logger.info(f"Attempting to connect to Kafka at {Config.KAFKA_BOOTSTRAP_SERVERS}")
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
            self.connection_details = "Connected to Kafka successfully"
            logger.info(self.connection_details)
            return True
        except Exception as e:
            self.connection_details = f"Failed to connect to Kafka: {str(e)}"
            logger.error(self.connection_details)
            self.producer = None
            return False

    def send_metric(self, metric_data: Dict[str, Any]) -> bool:
        """
        Send metric data to Kafka topic
        Returns True if sent successfully, False otherwise
        """
        if not self.producer:
            if not self._initialize_producer():
                logger.error(f"Kafka producer not available: {self.connection_details}")
                return False

        try:
            if self.producer:  # Double-check as _initialize_producer might have failed
                future = self.producer.send(
                    Config.KAFKA_TOPIC,
                    value=metric_data
                )
                # Wait for the message to be delivered
                record_metadata = future.get(timeout=2)
                logger.debug(f"Sent metric to Kafka topic={record_metadata.topic} partition={record_metadata.partition} offset={record_metadata.offset}")
                return True
            return False
        except KafkaError as e:
            logger.error(f"Error sending metric to Kafka: {str(e)}")
            self.producer = None  # Reset producer to trigger reconnection
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
            self.producer.close()
            self.producer = None