# Metrics Collection API

A robust Flask application designed for efficient metrics collection and management, integrating TypeScript client metrics, Confluent Kafka message forwarding, and Prometheus metric exposure.

## Features

- REST API endpoints for metrics collection
- Confluent Kafka integration with Avro schema support
- Prometheus metrics exposure
- Swagger UI for API documentation
- Health check endpoints
- Development mode support

## Tech Stack

- Flask web framework
- Confluent Kafka with Avro serialization
- Prometheus metrics
- RESTful API design
- TypeScript client integration

## Setup

1. Clone the repository
2. Create a `.env` file based on the provided example
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure Kafka and Schema Registry:
   - Ensure Confluent Kafka is running
   - Configure Schema Registry URL
   - Set up Kerberos authentication if required

5. Run the application:
   ```bash
   python main.py
   ```

## Metric Schema

The application uses Avro schema for metric serialization. The schema is defined in `schemas/metric.avsc`:

```json
{
  "type": "record",
  "name": "Metric",
  "namespace": "com.metrics.collection",
  "fields": [
    {
      "name": "name",
      "type": "string",
      "doc": "Name of the metric"
    },
    {
      "name": "value",
      "type": "double",
      "doc": "Value of the metric"
    },
    {
      "name": "timestamp",
      "type": "long",
      "doc": "Unix timestamp in milliseconds"
    },
    {
      "name": "tags",
      "type": {
        "type": "map",
        "values": "string"
      },
      "default": {},
      "doc": "Additional metric tags"
    },
    {
      "name": "profileId",
      "type": "string",
      "doc": "Profile identifier"
    }
  ]
}
```

## API Documentation

Access the Swagger UI documentation at `/swagger-ui` when the application is running.

## Monitoring

- Health check endpoint: `/api/v2/app/{app_id}/health`
- Prometheus metrics: `/prometheus-metrics`

## Development

The application supports a development mode that can be enabled by setting `FLASK_ENV=development` in your `.env` file.

## Kafka Authentication

The application supports Kerberos authentication for Kafka. Configure the following environment variables:

```env
KAFKA_SECURITY_PROTOCOL=SASL_PLAINTEXT
KAFKA_SASL_MECHANISM=GSSAPI
KAFKA_SERVICE_NAME=kafka
```

## Example Metric Submission

Here's how to submit metrics that comply with the Avro schema:

```python
import time
import requests

# Single metric example
metric = {
    "name": "cpu_usage",
    "value": 75.5,
    "timestamp": int(time.time() * 1000),
    "tags": {
        "host": "server1",
        "environment": "production"
    },
    "profileId": "profile123"
}

# Submit metric batch
metrics_batch = {
    "metrics": [metric]
}

# Send metrics to the API
response = requests.post(
    'http://localhost:5000/api/v2/app/your-app-id/metrics',
    json=metrics_batch
)

# The metrics will be:
# 1. Serialized using Avro schema
# 2. Sent to Kafka
# 3. Consumed and exposed via Prometheus at /prometheus-metrics
```

## Testing the Setup

1. First, verify the Kafka connection using the health check endpoint:
   ```bash
   curl http://localhost:5000/api/v2/app/your-app-id/health
   ```

2. Submit a test metric:
   ```python
   import time
   import requests

   # Single metric example
   metric = {
       "name": "cpu_usage",
       "value": 75.5,
       "timestamp": int(time.time() * 1000),
       "tags": {
           "host": "server1",
           "environment": "production"
       },
       "profileId": "profile123"
   }

   # Submit metric batch
   metrics_batch = {
       "metrics": [metric]
   }

   # Send metrics to the API
   response = requests.post(
       'http://localhost:5000/api/v2/app/your-app-id/metrics',
       json=metrics_batch
   )
   print(f"Response status: {response.status_code}")
   ```

3. Verify metrics in Prometheus format:
   ```bash
   curl http://localhost:5000/prometheus-metrics
   ```

   Expected output:
   ```
   # HELP client_metric_cpu_usage Client metric: cpu_usage
   # TYPE client_metric_cpu_usage gauge
   client_metric_cpu_usage{host="server1",environment="production"} 75.5

   # HELP kafka_metrics_consumed_total Total metrics consumed from Kafka
   # TYPE kafka_metrics_consumed_total counter
   kafka_metrics_consumed_total 1
   ```

4. Check the consumer metrics:
   ```bash
   curl http://localhost:5000/api/v2/app/your-app-id/metrics
   ```

## Troubleshooting

1. Kafka Connection Issues:
   - Verify Kafka bootstrap servers are accessible
   - Check Kerberos authentication configuration
   - Ensure Schema Registry is running and accessible

2. Metric Publishing Issues:
   - Validate metric format against Avro schema
   - Check Kafka producer logs for delivery errors
   - Verify consumer group ID and offset configuration

3. Prometheus Metrics:
   - Ensure metrics are being exposed at `/prometheus-metrics`
   - Check metric naming follows Prometheus conventions
   - Verify label values are properly escaped