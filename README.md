# Metrics Collection API

A robust Flask application designed for efficient metrics collection and management, integrating TypeScript client metrics, Kafka message forwarding, and Prometheus metric exposure.

## Features

- REST API endpoints for metrics collection
- Kafka integration for message queuing
- Prometheus metrics exposure
- Swagger UI for API documentation
- Health check endpoints
- Development mode support

## Tech Stack

- Flask web framework
- Kafka for message queuing
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

4. Run the application:
   ```bash
   python main.py
   ```

## API Documentation

Access the Swagger UI documentation at `/api/swagger-ui` when the application is running.

## Monitoring

- Health check endpoint: `/health`
- Prometheus metrics: `/prometheus-metrics`

## Development

The application supports a development mode that can be enabled by setting `FLASK_ENV=development` in your `.env` file. This mode disables Kafka integration for easier local development.
