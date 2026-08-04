#!/bin/bash

# Memeriksa apakah pengguna memasukkan argumen
if [ "$1" == "up" ]; then
    echo "Initiating compose for LLM"
    docker compose --env-file .env -f ./deployment/compose/docker-compose.frontend.yaml up
elif [ "$1" == "build" ]; then
    echo "Rebuilding and initiating compose for LLM"
    # Tambahkan --build di sini untuk menerapkan perubahan kode baru
    docker compose --env-file .env -f ./deployment/compose/docker-compose.frontend.yaml up --build
elif [ "$1" == "down" ]; then
    echo "Stopping compose for LLM"
    docker compose --env-file .env -f ./deployment/compose/docker-compose.frontend.yaml down
else
    echo "Wrong usage. Usage: ./manage-frontend.sh [up|build|down]"
fi