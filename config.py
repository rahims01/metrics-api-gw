import os
from dotenv import load_dotenv
import logging.config

load_dotenv()

class Config:
    # Environment
    ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # Flask Configuration
    SECRET_KEY = os.environ.get("SESSION_SECRET", os.urandom(32))

    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'metrics')
    KAFKA_CLIENT_ID = os.getenv('KAFKA_CLIENT_ID', 'metrics-collector')

    # Application Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    METRICS_BATCH_SIZE = int(os.getenv('METRICS_BATCH_SIZE', '100'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '5'))

    # Security
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

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