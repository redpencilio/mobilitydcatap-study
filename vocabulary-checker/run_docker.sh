#!/bin/bash

# Build the Docker image (force rebuild without cache)
docker build --no-cache -t dcat-vocab-checker .

# Run the container with host network access
# Use --add-host on Linux to access host services
docker run -it --rm \
    --add-host=host.docker.internal:host-gateway \
    dcat-vocab-checker

# Alternative for macOS/Windows (host.docker.internal works by default):
# docker run -it --rm dcat-vocab-checker