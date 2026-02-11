#!/bin/sh
set -e

RUN_MODE="NORMAL"
LOCK_FILE="/var/run/agentscope_first_run.lock"

if [ "$BUILT_BY_SCRIPT" = "true" ]; then
    echo "--> 'BUILT_BY_SCRIPT' flag detected. Activating advanced run-mode detection."
    if [ ! -f "$LOCK_FILE" ]; then
        RUN_MODE="HEALTH_CHECK"
        echo "--> First run under build script detected (Health Check Mode). Creating lock file..."
        mkdir -p "$(dirname "$LOCK_FILE")"
        touch "$LOCK_FILE"
    else
        RUN_MODE="NORMAL"
        echo "--> Subsequent run under build script detected (Normal Mode)."
    fi
else
    echo "--> 'BUILT_BY_SCRIPT' flag not found. Assuming standard Normal Mode."
    RUN_MODE="NORMAL"
fi

echo "--- Phase 1: Starting internal Docker Daemon ---"
dockerd-entrypoint.sh &
dockerd_pid=$!
while ! docker info > /dev/null 2>&1; do
    echo "Waiting for internal Docker Daemon..."
    sleep 2
done
echo "--> Internal Docker Daemon is UP!"

echo "--- Phase 2: Loading and starting nested Redroid container ---"
REDROID_IMAGE="agentscope/redroid:internal"

if [ -z "$(docker images -q "$REDROID_IMAGE")" ]; then
    if [ -f /redroid.tar ]; then
        echo "--> Loading Redroid image from /redroid.tar..."
        docker load -i /redroid.tar
        echo "--> Successfully loaded Redroid image."
        if [ "$RUN_MODE" = "NORMAL" ]; then
            echo "--> Normal mode: Removing /redroid.tar."
            rm /redroid.tar
        else # RUN_MODE is "HEALTH_CHECK"
            echo "--> Health check mode: Preserving /redroid.tar for commit."
        fi
    else
        echo "[FATAL ERROR] Built-in /redroid.tar not found!"
        exit 1
    fi
else
    echo "--> Redroid image already exists."
fi

if [ -z "$(docker images -q "$REDROID_IMAGE")" ]; then
    echo "[FATAL ERROR] Failed to load Redroid image '$REDROID_IMAGE' from tarball."
    exit 1
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

echo "--- Phase 2.5: Waiting for devices and cleaning up ---"
ATTEMPTS=0
MAX_ATTEMPTS=60

while [ ${ATTEMPTS} -lt ${MAX_ATTEMPTS} ]; do
    DEVICES_LIST=$(adb devices || true)

    if [ -z "$DEVICES_LIST" ]; then
        echo "Warning: 'adb devices' returned empty. ADB server might be down. Retrying..."
        adb kill-server || true
        sleep 2
        ATTEMPTS=$((ATTEMPTS + 1))
        continue
    fi

    MANUAL_DEVICE_FOUND=$(echo "${DEVICES_LIST}" | grep "localhost:5555" | wc -l)
    AUTO_DEVICE_FOUND=$(echo "${DEVICES_LIST}" | grep "emulator-5554" | wc -l)

    echo "Polling devices... Found: Manual(${MANUAL_DEVICE_FOUND}), Auto(${AUTO_DEVICE_FOUND})"

    adb connect localhost:5555 > /dev/null 2>&1 || true

    if [ "${MANUAL_DEVICE_FOUND}" -gt 0 ] && [ "${AUTO_DEVICE_FOUND}" -gt 0 ]; then
        echo "--> Both devices are present. Cleaning up..."
        adb disconnect localhost:5555 || true
        echo "--> Cleanup complete."
        # Ensure emulator-5554 is in 'device' state before proceeding
        EMU_STATE=$(echo "${DEVICES_LIST}" | awk '/emulator-5554/ {print $2}')
        if [ "${EMU_STATE}" = "device" ]; then
            break
        else
            echo "emulator-5554 is present but not in 'device' state (current state: ${EMU_STATE}). Waiting..."
        fi
    fi

    sleep 2
    ATTEMPTS=$((ATTEMPTS + 1))
done

if [ ${ATTEMPTS} -ge ${MAX_ATTEMPTS} ]; then
    echo "[FATAL ERROR] Timed out waiting for both ADB devices to appear."
    echo "Final device list:"
    adb devices -l || true
    echo "Redroid container status:"
    docker ps -a -f name=redroid_nested
    exit 1
fi

echo "--> Final, clean devices list before starting services:"
adb devices -l

echo "--- Phase 3: Starting Application Services ---"
mkdir -p /etc/supervisor/conf.d/
export SECRET_TOKEN="${SECRET_TOKEN:-secret_token123}"
envsubst '${SECRET_TOKEN}' < /etc/supervisor/supervisord.conf.template > /etc/supervisor/conf.d/supervisord.conf
if [ -f /etc/nginx/nginx.conf.template ]; then
  export NGINX_TIMEOUT=${NGINX_TIMEOUT:-60}
  envsubst '$SECRET_TOKEN $NGINX_TIMEOUT' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf
fi
/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

sleep 5
echo "--> Nginx & FastAPI & WS-Scrcpy services started."
supervisorctl status

echo "--> Orchestration complete. System is fully operational."
wait $dockerd_pid