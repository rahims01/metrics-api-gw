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

def validate_kafka_connection(bootstrap_servers: str) -> tuple[bool, str]:
    """Validate if any Kafka host is reachable"""
    if not bootstrap_servers:
        return False, "No Kafka bootstrap servers configured"

    servers = bootstrap_servers.split(',')
    reachable_servers = []
    unreachable_servers = []

    for server in servers:
        try:
            host, port_str = server.strip().split(':')
            port = int(port_str)

            try:
                ip_address = socket.gethostbyname(host)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((ip_address, port))
                sock.close()

                if result == 0:
                    reachable_servers.append(f"{host}:{port}")
                else:
                    unreachable_servers.append(f"{host}:{port} (error code: {result})")
            except socket.gaierror:
                unreachable_servers.append(f"{host}:{port} (DNS resolution failed)")
            except Exception as e:
                unreachable_servers.append(f"{host}:{port} (error: {str(e)})")

        except ValueError:
            unreachable_servers.append(f"{server} (invalid format)")
            continue

    if reachable_servers:
        status = f"Reachable Kafka servers: {', '.join(reachable_servers)}"
        if unreachable_servers:
            status += f"\nUnreachable servers: {', '.join(unreachable_servers)}"
        return True, status
    else:
        return False, f"No reachable Kafka servers. Errors: {', '.join(unreachable_servers)}"

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
    KAFKA_SECURITY_PROTOCOL = get_env_var('KAFKA_SECURITY_PROTOCOL', 'SASL_PLAINTEXT')
    KAFKA_SASL_MECHANISM = get_env_var('KAFKA_SASL_MECHANISM', 'GSSAPI')
    KAFKA_SERVICE_NAME = get_env_var('KAFKA_SERVICE_NAME', 'kafka')

    # Schema Registry Configuration
    SCHEMA_REGISTRY_URL = get_env_var('SCHEMA_REGISTRY_URL', 'http://localhost:8081')

    # Application Configuration
    LOG_LEVEL = get_env_var('LOG_LEVEL', 'DEBUG')
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
is_reachable, kafka_status = validate_kafka_connection(Config.KAFKA_BOOTSTRAP_SERVERS)

# Log configuration status
logger.info(f"Environment: {Config.ENV}")
logger.info(f"Debug mode: {Config.DEBUG}")
logger.info(f"Log level: {Config.LOG_LEVEL}")
logger.info(f"CORS origins: {Config.CORS_ORIGINS}")
logger.info(f"Metrics batch size: {Config.METRICS_BATCH_SIZE}")
logger.info(f"Maximum payload size: {Config.MAX_PAYLOAD_SIZE}")
logger.info(f"Kafka connection status: {kafka_status}")
logger.info(f"Kafka topic: {Config.KAFKA_TOPIC}")
logger.info(f"Schema Registry URL: {Config.SCHEMA_REGISTRY_URL}")
logger.info(f"App ID: {Config.APP_ID}")