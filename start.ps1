# HanClipper - Quick Start Script for PowerShell

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  HanClipper - AI Video Clipping Tool" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create a .env file with your API keys:"
    Write-Host "  1. Copy the template: copy .env.example .env"
    Write-Host "  2. Edit .env and add your API keys"
    Write-Host ""
    exit 1
}

# Check if Docker is running
Write-Host "Checking if Docker is running..."
& docker info >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Determine docker compose command
$dockerComposeCmd = "docker compose"
& docker compose version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    & docker-compose version >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerComposeCmd = "docker-compose"
    } else {
        Write-Host "Error: Docker Compose is not installed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Starting HanClipper..." -ForegroundColor Green
Write-Host ""

# Build and start containers
Write-Host "Building and starting Docker containers..."
Write-Host "(This may take a few minutes on the first run)"
Write-Host ""

if ($dockerComposeCmd -eq "docker compose") {
    docker compose up -d --build
} else {
    docker-compose up -d --build
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "HanClipper is starting up!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Services will be available at:"
    Write-Host "  - Frontend:  http://localhost:3107"
    Write-Host "  - Backend:   http://localhost:8000"
    Write-Host "  - API Docs:  http://localhost:8000/docs"
    Write-Host ""
    Write-Host "To view logs, run:"
    Write-Host "  $dockerComposeCmd logs -f"
    Write-Host ""
    Write-Host "To stop all services, run:"
    Write-Host "  $dockerComposeCmd down"
    Write-Host ""
    Write-Host "Waiting for services to be healthy..."
    
    Start-Sleep -Seconds 5
    Write-Host "Services are starting! If you encounter issues, check the logs." -ForegroundColor Green
} else {
    Write-Host "Error: Failed to start Docker containers." -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
