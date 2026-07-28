#!/bin/bash

echo "Rebuilding system from scratch..."

docker-compose down
docker-compose build --no-cache

echo "Rebuild complete."