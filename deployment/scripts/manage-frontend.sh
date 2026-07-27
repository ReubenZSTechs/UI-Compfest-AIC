#!/bin/bash

# Memeriksa apakah pengguna memasukkan argumen (up atau down)
if [ "$1" == "up" ]; then
    echo "Initiating compose for LLM"
    docker compose --env-file .env -f ./deployment/compose/docker-compose_frontend.yaml up
elif [ "$1" == "down" ]; then
    echo "Stopping compose for LLM"
    docker compose --env-file .env -f ./deployment/compose/docker-compose_frontend.yaml down
else
    echo "Wrong usage. Usage: ./manage-frontend.sh [up|down]"
fi