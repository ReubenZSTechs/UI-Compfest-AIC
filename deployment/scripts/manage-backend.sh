#!/bin/bash

# deployment/scripts/manage-backend.sh
COMPOSE_FILE="./deployment/compose/docker-compose_backend.yaml"
ENV_FILE="./backend/.env"

if [ "$1" == "up" ]; then
    echo "Starting compose for backend"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

elif [ "$1" == "down" ]; then
    echo "Stopping compose for backend"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down

elif [ "$1" == "restart" ]; then
    echo "Restarting compose for backend"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" restart

elif [ "$1" == "build" ]; then
    echo "Building image for backend"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build

elif [ "$1" == "logs" ]; then
    echo "Showing logs for backend"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs -f --tail=200

elif [ "$1" == "ps" ]; then
    echo "Showing container status for backend"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

else
    echo "Wrong usage. Usage: ./manage-backend.sh [up|down|restart|build|logs|ps]"
fi