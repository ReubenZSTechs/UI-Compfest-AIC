#!/bin/bash

set -e

echo "Deploying system..."

docker-compose pull
docker-compose build --no_cache
docker-compose up

echo "Deployment complete."