#!/bin/bash
# SAP App Builder - Deployment Script
# Usage: ./scripts/deploy.sh [production|staging]

set -e

ENVIRONMENT=${1:-production}
IMAGE_NAME="sap-app-builder"
IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

echo "🚀 SAP App Builder Deployment"
echo "Environment: $ENVIRONMENT"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"
echo ""

# Build the image
echo "📦 Building Docker image..."
docker build -t $IMAGE_NAME:$IMAGE_TAG -t $IMAGE_NAME:latest .

# Run tests
echo "🧪 Running tests..."
docker run --rm $IMAGE_NAME:$IMAGE_TAG python -m pytest backend/tests -v --tb=short

# Deploy based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    echo "🌐 Deploying to production..."
    docker-compose up -d app
elif [ "$ENVIRONMENT" = "staging" ]; then
    echo "🔧 Deploying to staging..."
    docker-compose --profile staging up -d
else
    echo "❌ Unknown environment: $ENVIRONMENT"
    exit 1
fi

echo ""
echo "✅ Deployment complete!"
echo "App running at: http://localhost:8000"
echo "API docs at: http://localhost:8000/api/docs"
