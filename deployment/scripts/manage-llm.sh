#!/bin/bash

# Memeriksa apakah pengguna memasukkan argumen (up atau down)
if [ "$1" == "up" ]; then
    echo "Initiating compose for LLM"
    docker compose --env-file .env -f ./deployment/compose/docker-compose_llm.yaml up
elif [ "$1" == "down" ]; then
    echo "Stopping compose for LLM"
    docker compose --env-file .env -f ./deployment/compose/docker-compose_llm.yaml down
else
    echo "Wrong usage. Usage: ./manage-llm.sh [up|down]"
fi