import json
import logging
from typing import Optional
from kafka import KafkaConsumer
from prometheus_client import Counter, Gauge, Histogram
from config import Config

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self):
        self.consumer: Optional[KafkaConsumer] = None
        self.dev_mode = Config.ENV == 'development'
        
        # Prometheus metrics for consumed data
        self.metrics_consumed = Counter('metrics_consumed_total', 'Total metrics consumed from Kafka')
        self.latest_metric_value = Gauge('latest_metric_value', 'Latest value for each metric', ['name'])
        self.metric_processing_time = Histogram('metric_processing_seconds', 'Time spent processing consumed metrics')
        
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
                with self.metric_processing_time.time():
                    try:
                        metric_data = message.value
                        if isinstance(metric_data, dict) and 'name' in metric_data and 'value' in metric_data:
                            # Update Prometheus metrics
                            self.metrics_consumed.inc()
                            self.latest_metric_value.labels(name=metric_data['name']).set(float(metric_data['value']))
                            logger.debug(f"Processed metric: {metric_data['name']} = {metric_data['value']}")
                    except Exception as e:
                        logger.error(f"Error processing metric: {str(e)}")

        except Exception as e:
            logger.error(f"Error consuming from Kafka: {str(e)}")
        finally:
            self.close()

    def close(self):
        """Close the Kafka consumer"""
        if self.consumer:
            self.consumer.close()
            self.consumer = None
