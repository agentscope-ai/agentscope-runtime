#!/bin/sh
set -e

echo "===== Self-Contained & Optimized Orchestrator (v-Final Perfected) ====="

echo "--- Phase 1: Starting internal Docker Daemon ---"
dockerd-entrypoint.sh &
dockerd_pid=$!
while ! docker info > /dev/null 2>&1; do
    echo "Waiting for internal Docker Daemon..."
    sleep 2
done
echo "--> Internal Docker Daemon is UP!"

echo "--- Phase 2: Loading and starting nested Redroid container ---"
REDROID_IMAGE="redroid/redroid:11.0.0-240527"

if [ -z "$(docker images -q "$REDROID_IMAGE")" ]; then
    if [ -f /redroid.tar ]; then
        echo "--> Loading Redroid image from /redroid.tar..."
        docker load -i /redroid.tar
        echo "--> Successfully loaded Redroid image."
        rm /redroid.tar
    else
        echo "[FATAL ERROR] Built-in /redroid.tar not found!"
        exit 1
    fi
else
    echo "--> Redroid image already exists."
fi

if [ "$(docker ps -q -f name=redroid_nested)" ]; then
    echo "Nested redroid container is already running."
else
    echo "--> Starting nested redroid container..."
    docker run -d --rm --privileged \
        --name redroid_nested \
        -p 127.0.0.1:5555:5555 \
        "$REDROID_IMAGE"
fi

echo "--> Waiting for nested Redroid's ADB to be ready..."
while true; do
    if adb connect localhost:5555 > /dev/null 2>&1 && [ "$(adb get-state)" = "device" ]; then
        echo "--> Nested Redroid is ready and connected via ADB."
        break
    fi
    sleep 2
done
adb devices -l

echo "--- Phase 3: Starting Application Services ---"

mkdir -p /etc/supervisor/conf.d/

export SECRET_TOKEN="${SECRET_TOKEN:-secret_token123}"
envsubst '${SECRET_TOKEN}' < /etc/supervisor/supervisord.conf.template > /etc/supervisor/conf.d/supervisord.conf
/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

sleep 5
echo "--> Nginx & FastAPI services started."
supervisorctl status

echo "--> Orchestration complete. System is fully operational."
wait $dockerd_pid
