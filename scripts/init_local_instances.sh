#!/usr/bin/env bash
# ==============================================================================
# LongTail Passport - Local Real Instances Bootstrap Script
# Boots Ghost, Lemmy, PostgreSQL, MinIO, and MockHub via Docker Compose.
# ==============================================================================

set -euo pipefail

echo "==> Starting LongTail Passport core services and real instances..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    exit 1
fi

docker compose --profile real-instances up -d

echo "==> Waiting for Ghost Admin API (http://localhost:2368)..."
MAX_RETRIES=30
RETRY=0
until curl -s http://localhost:2368/ghost/api/admin/site/ &> /dev/null || [ $RETRY -eq $MAX_RETRIES ]; do
    RETRY=$((RETRY + 1))
    echo "    Waiting for Ghost ($RETRY/$MAX_RETRIES)..."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "WARN: Ghost did not become ready in time, continuing..."
else
    echo "==> Ghost is ready at http://localhost:2368."
fi

echo "==> Waiting for Lemmy (http://localhost:8536)..."
RETRY=0
until curl -s http://localhost:8536/api/v3/site &> /dev/null || [ $RETRY -eq $MAX_RETRIES ]; do
    RETRY=$((RETRY + 1))
    echo "    Waiting for Lemmy ($RETRY/$MAX_RETRIES)..."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "WARN: Lemmy did not become ready in time, continuing..."
else
    echo "==> Lemmy is ready at http://localhost:8536."
fi

echo "==> All local instances initialized successfully."
