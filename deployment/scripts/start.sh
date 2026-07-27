#!/bin/bash

echo "Starting full LLM system..."

docker-compose up

echo "System running:"
echo "Frontend: http://localhost:8080"
echo "Backend: http://localhost:8000"