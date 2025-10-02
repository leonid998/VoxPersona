#!/bin/bash

# VoxPersona Docker Build Optimization Test Script
# Enables BuildKit and runs validation tests

set -e

echo "VoxPersona Docker Build Optimization Validation"
echo "============================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Set Python command
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Enable BuildKit
export DOCKER_BUILDKIT=1

echo "Using Docker BuildKit for optimized builds"
echo "Python command: $PYTHON_CMD"
echo ""

# Run the validation script
$PYTHON_CMD validate_docker_optimization.py "$@"

echo ""
echo "Validation completed!"
echo ""
echo "To manually test build performance:"
echo "  1. Clean build:       DOCKER_BUILDKIT=1 docker build --no-cache -t voxpersona:latest ."
echo "  2. Incremental build: DOCKER_BUILDKIT=1 docker build -t voxpersona:latest ."
echo "  3. View layers:       docker history voxpersona:latest"
echo "  4. Check image size:  docker images voxpersona:latest"