# Python Version Requirements

## Project Python Version: 3.10.11

This project is **strictly fixed** on Python 3.10.11 for the following reasons:

### Compatibility Issues Solved:
1. **Audio Processing**: Python 3.13+ removes the `audioop` module which is required by `pydub`
2. **Library Dependencies**: All dependencies in `requirements.txt` are tested and verified with Python 3.10.11
3. **Server Compatibility**: Production server runs Python 3.10.12, so 3.10.11 ensures maximum compatibility

### Version Enforcement:
- **Local Development**: `.python-version` file specifies 3.10.11
- **Docker**: `Dockerfile` uses `python:3.10.11-slim` base image
- **GitHub Actions**: All workflows use Python 3.10.11
- **CI/CD Pipeline**: Version verification checks ensure consistency

### DO NOT UPGRADE TO:
- ❌ Python 3.13+ (audioop module removed)
- ❌ Python 3.12+ (potential compatibility issues with some dependencies)

### Verified Compatible Versions:
- ✅ Python 3.10.11 (current, recommended)
- ✅ Python 3.10.12 (server version, compatible)

## Installation Instructions:

### Using pyenv:
```bash
pyenv install 3.10.11
pyenv local 3.10.11
```

### Using conda:
```bash
conda install python=3.10.11
```

### Verification:
```bash
python --version  # Should output: Python 3.10.11
```

## Troubleshooting:

If you encounter version-related issues:
1. Check your Python version: `python --version`
2. Verify `.python-version` file exists and contains `3.10.11`
3. Ensure all virtual environments use Python 3.10.11
4. Check GitHub Actions logs for version verification steps

## Update History:
- 2025-01-22: Fixed all configurations to use Python 3.10.11
- 2025-01-22: Added version verification to CI/CD pipelines