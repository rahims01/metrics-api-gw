import os
import socket
from dotenv import load_dotenv
import logging.config
from typing import Any, Optional

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

def validate_kafka_connection(host: str, port: int) -> tuple[bool, str]:
    """Validate if Kafka host is reachable"""
    try:
        # Try to resolve the hostname first
        ip_address = socket.gethostbyname(host)
        logger.info(f"Resolved Kafka host {host} to IP: {ip_address}")

        # Try to establish a TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        result = sock.connect_ex((ip_address, port))
        sock.close()

        if result == 0:
            return True, f"Kafka host {host}:{port} ({ip_address}) is reachable"
        else:
            return False, f"Cannot connect to Kafka host {host}:{port} ({ip_address}), error code: {result}"
    except socket.gaierror:
        return False, f"Cannot resolve Kafka hostname: {host}"
    except Exception as e:
        return False, f"Error checking Kafka connection: {str(e)}"

class Config:        
    """Application configuration"""

    # Environment
    ENV = get_env_var('FLASK_ENV', 'development')
    DEBUG = get_bool_env_var('FLASK_DEBUG', False)

    # Flask Configuration
    SECRET_KEY = get_env_var('SESSION_SECRET', required=True)

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = get_env_var('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    KAFKA_TOPIC = get_env_var('KAFKA_TOPIC', 'metrics')
    KAFKA_CLIENT_ID = get_env_var('KAFKA_CLIENT_ID', 'metrics-collector')

    # Application Configuration
    LOG_LEVEL = get_env_var('LOG_LEVEL', 'DEBUG')
    METRICS_BATCH_SIZE = get_int_env_var('METRICS_BATCH_SIZE', 100000)
    REQUEST_TIMEOUT = get_int_env_var('REQUEST_TIMEOUT', 5)
    APP_ID = get_env_var('APP_ID', 'default-app-id')

    # Batch Processing Configuration
    MAX_PAYLOAD_SIZE = get_int_env_var('MAX_PAYLOAD_SIZE', 100 * 1024 * 1024)  # 100MB default

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

# Validate Kafka connection
kafka_host = Config.KAFKA_BOOTSTRAP_SERVERS.split(':')[0]
kafka_port = int(Config.KAFKA_BOOTSTRAP_SERVERS.split(':')[1])
is_reachable, kafka_status = validate_kafka_connection(kafka_host, kafka_port)

# Log configuration status
logger.info(f"Environment: {Config.ENV}")
logger.info(f"Debug mode: {Config.DEBUG}")
logger.info(f"Log level: {Config.LOG_LEVEL}")
logger.info(f"CORS origins: {Config.CORS_ORIGINS}")
logger.info(f"Metrics batch size: {Config.METRICS_BATCH_SIZE}")
logger.info(f"Maximum payload size: {Config.MAX_PAYLOAD_SIZE}")
logger.info(f"Kafka connection status: {kafka_status}")
logger.info(f"Kafka topic: {Config.KAFKA_TOPIC}")
logger.info(f"App ID: {Config.APP_ID}")