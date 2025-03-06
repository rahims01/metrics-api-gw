import os
import logging.config
from typing import Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_env_var(key: str, default: Any = None, required: bool = False) -> Optional[str]:
    """Helper to get environment variables with validation"""
    value = os.getenv(key, default)
    if required and value is None:
        raise ValueError(f"Required environment variable '{key}' is not set")
    return value

class Config:        
    """Application configuration"""

    # Environment
    ENV = get_env_var('FLASK_ENV', 'development')
    DEBUG = get_env_var('FLASK_DEBUG', 'True').lower() == 'true'

    # Flask Configuration
    SECRET_KEY = get_env_var('SESSION_SECRET', required=True)

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = get_env_var('KAFKA_BOOTSTRAP_SERVERS', required=True)
    KAFKA_TOPIC = get_env_var('KAFKA_TOPIC', 'metrics')
    KAFKA_CLIENT_ID = get_env_var('KAFKA_CLIENT_ID', 'metrics-collector')

    # Kafka Security Configuration (SASL_SSL with GSSAPI)
    KAFKA_SECURITY_PROTOCOL = 'SASL_SSL'
    KAFKA_SASL_MECHANISM = 'GSSAPI'
    KAFKA_SASL_KERBEROS_SERVICE_NAME = 'kafka'
    KAFKA_SASL_KERBEROS_DOMAIN_NAME = get_env_var('KAFKA_SASL_KERBEROS_DOMAIN_NAME', required=True)

    # Kerberos Configuration
    KRB5_CONFIG = get_env_var('KRB5_CONFIG', '/etc/krb5.conf')
    KRB5_KTNAME = get_env_var('KRB5_KTNAME', required=True)
    KRB5_CLIENT_KTNAME = get_env_var('KRB5_CLIENT_KTNAME', required=True)

    # Application Configuration
    LOG_LEVEL = get_env_var('LOG_LEVEL', 'DEBUG')
    METRICS_BATCH_SIZE = 10000  # Maximum number of metrics to store in memory

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
            }
        }
    }

# Initialize logging configuration
logging.config.dictConfig(Config.LOGGING_CONFIG)
logger = logging.getLogger(__name__)