# SAP App Builder - Deployment Script (Windows)
# Usage: .\scripts\deploy.ps1 [-Environment production]

param(
    [string]$Environment = "production"
)

$ErrorActionPreference = "Stop"

$ImageName = "sap-app-builder"
$ImageTag = git rev-parse --short HEAD 2>$null
if (-not $ImageTag) { $ImageTag = "latest" }

Write-Host "🚀 SAP App Builder Deployment" -ForegroundColor Cyan
Write-Host "Environment: $Environment"
Write-Host "Image: ${ImageName}:${ImageTag}"
Write-Host ""

# Build the image
Write-Host "📦 Building Docker image..." -ForegroundColor Yellow
docker build -t "${ImageName}:${ImageTag}" -t "${ImageName}:latest" .

# Run tests
Write-Host "🧪 Running tests..." -ForegroundColor Yellow
docker run --rm $ImageName python -m pytest backend/tests -v --tb=short

# Deploy
if ($Environment -eq "production") {
    Write-Host "🌐 Deploying to production..." -ForegroundColor Green
    docker-compose up -d app
} elseif ($Environment -eq "staging") {
    Write-Host "🔧 Deploying to staging..." -ForegroundColor Blue
    docker-compose --profile staging up -d
} else {
    Write-Host "❌ Unknown environment: $Environment" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host "App running at: http://localhost:8000"
Write-Host "API docs at: http://localhost:8000/api/docs"
