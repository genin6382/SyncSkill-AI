#!/bin/bash

echo "Waiting for MySQL to be ready..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  echo "Waiting..."
  sleep 2
done
echo "MySQL is up - setting up ChromaDB..."

# Check if ChromaDB collection already exists
if [ ! -d "/app/chroma_db" ] || [ -z "$(ls -A /app/chroma_db 2>/dev/null)" ]; then
  echo "Setting up ChromaDB for the first time..."
  if [ -f "/app/new_job_dataset.csv" ]; then
    python chroma_setup.py
  else
    echo "Warning: new_job_dataset.csv not found. ChromaDB setup may fail."
    python chroma_setup.py
  fi
else
  echo "ChromaDB already exists, skipping setup."
fi

echo "Starting Flask"
exec "$@"
