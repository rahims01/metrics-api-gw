import os
from typing import Any, Optional
from dotenv import load_dotenv
import logging.config

# Load environment variables from .env file
load_dotenv()

def get_env_var(key: str, default: Any = None, required: bool = False) -> Optional[str]:
    """Helper to get environment variables with validation"""
    value = os.getenv(key, default)
    if required and value is None:
        raise ValueError(f"Required environment variable '{key}' is not set")
    return value

def get_bool_env_var(key: str, default: bool = False) -> bool:
    """Helper to get boolean environment variables"""
    return str(get_env_var(key, default)).lower() in ('true', '1', 't', 'yes')

def get_int_env_var(key: str, default: int) -> int:
    """Helper to get integer environment variables"""
    try:
        return int(get_env_var(key, default))
    except (TypeError, ValueError):
        return default

class Config:
    """Application configuration"""

    # Environment
    ENV = get_env_var('FLASK_ENV', 'production')
    DEBUG = get_bool_env_var('FLASK_DEBUG', False)

    # Flask Configuration
    SECRET_KEY = get_env_var('SESSION_SECRET', required=True)

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = get_env_var('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    KAFKA_TOPIC = get_env_var('KAFKA_TOPIC', 'metrics')
    KAFKA_CLIENT_ID = get_env_var('KAFKA_CLIENT_ID', 'metrics-collector')

    # Application Configuration
    LOG_LEVEL = get_env_var('LOG_LEVEL', 'INFO')
    METRICS_BATCH_SIZE = get_int_env_var('METRICS_BATCH_SIZE', 100)
    REQUEST_TIMEOUT = get_int_env_var('REQUEST_TIMEOUT', 5)

    # Security
    CORS_ORIGINS = get_env_var('CORS_ORIGINS', '*').split(',')

    # Logging Configuration
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': LOG_LEVEL,
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['default'],
                'level': LOG_LEVEL,
                'propagate': True
            },
            'werkzeug': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
        }
    }

# Initialize logging configuration
logging.config.dictConfig(Config.LOGGING_CONFIG)

# Create logger for this module
logger = logging.getLogger(__name__)

# Log loaded configuration (excluding sensitive values)
logger.info(f"Environment: {Config.ENV}")
logger.info(f"Debug mode: {Config.DEBUG}")
logger.info(f"Log level: {Config.LOG_LEVEL}")
logger.info(f"CORS origins: {Config.CORS_ORIGINS}")
logger.info(f"Metrics batch size: {Config.METRICS_BATCH_SIZE}")
logger.info(f"Kafka bootstrap servers: {Config.KAFKA_BOOTSTRAP_SERVERS}")
logger.info(f"Kafka topic: {Config.KAFKA_TOPIC}")