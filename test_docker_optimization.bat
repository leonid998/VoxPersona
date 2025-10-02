@echo off
REM VoxPersona Docker Build Optimization Test Script for Windows
REM Enables BuildKit and runs validation tests

setlocal enabledelayedexpansion

echo VoxPersona Docker Build Optimization Validation
echo =============================================

REM Check if Docker is installed
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not installed or not running
    exit /b 1
)

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    python3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo Error: Python is not installed or not in PATH
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

REM Enable BuildKit
set DOCKER_BUILDKIT=1

echo Using Docker BuildKit for optimized builds
echo Python command: %PYTHON_CMD%
echo.

REM Run the validation script
%PYTHON_CMD% validate_docker_optimization.py %*

echo.
echo Validation completed!
echo.
echo To manually test build performance:
echo   1. Clean build:       set DOCKER_BUILDKIT=1 ^&^& docker build --no-cache -t voxpersona:latest .
echo   2. Incremental build: set DOCKER_BUILDKIT=1 ^&^& docker build -t voxpersona:latest .
echo   3. View layers:       docker history voxpersona:latest
echo   4. Check image size:  docker images voxpersona:latest

pause