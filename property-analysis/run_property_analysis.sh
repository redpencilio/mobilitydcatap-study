#!/bin/bash

# Build the Docker image for property analysis
docker build --no-cache -t property-analyzer -f Dockerfile .

# Run the container with host network access
# Use --add-host on Linux to access host services
docker run -it --rm \
    --add-host=host.docker.internal:host-gateway \
    property-analyzer

# Alternative for macOS/Windows (host.docker.internal works by default):
# docker run -it --rm property-analyzer
