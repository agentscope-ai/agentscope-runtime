# =================================================================
# Stage 1: adb-mcp builder
# =================================================================
FROM docker:28-dind AS node-builder

RUN apk update && apk add --no-cache nodejs-lts npm

WORKDIR /app/node_app
COPY src/agentscope_runtime/sandbox/box/mobile/adbmcp/package*.json ./

# Install all dependencies and build the application
RUN npm install
COPY src/agentscope_runtime/sandbox/box/mobile/adbmcp/ .
RUN npm run build

# Create a clean production-only package
RUN mkdir -p /prod_bundle && \
    cp -r dist/* /prod_bundle/ && \
    cp package*.json /prod_bundle/ && \
    cd /prod_bundle && \
    npm install --production

# =================================================================
# Stage 2: ws-scrcpy builder
# =================================================================
FROM docker:28-dind AS ws-scrcpy-builder

RUN apk update && apk add --no-cache \
    nodejs-lts npm git python3 build-base

WORKDIR /app
ARG WS_SCRCPY_COMMIT_SHA=ef273d97c6ac0c05d03b41d4b55d59a25b95c505
RUN git clone https://github.com/NetrisTV/ws-scrcpy.git \
    && cd ws-scrcpy \
    && git checkout ${WS_SCRCPY_COMMIT_SHA}

WORKDIR /app/ws-scrcpy
COPY src/agentscope_runtime/sandbox/box/mobile/box/index.ts /app/ws-scrcpy/src/app/index.ts

# Install all dependencies and build the application
RUN npm install && npm run dist

# Create a clean production-only package
RUN mkdir -p /prod_bundle && \
    cp -r dist/* /prod_bundle/ && \
    cd /prod_bundle && \
    npm install --production

# =================================================================
# Stage 3: Fetch Redroid Docker image (redroid-fetcher)
# =================================================================
FROM docker:28-dind AS redroid-fetcher

# NOTE:
# This stage secures the build process by pulling a third-party image (Redroid)
# using an immutable digest (SHA-256 hash) instead of a mutable tag. This prevents
# supply chain attacks where a tag could be retargeted to a malicious image.
#
# To achieve this, it starts a Docker daemon inside the build environment
# (Docker-in-Docker), pulls the specified Redroid image, and saves it as a tarball.
#
# --- DOCKER-IN-DOCKER PRIVILEGE WARNING ---
# This approach requires the build environment to support running a Docker daemon with
# sufficient privileges (e.g., privileged containers with proper cgroup access). In
# many CI/CD or restricted environments, such privileges may not be available, which
# can cause this stage to fail due to permission or daemon startup issues.
#
# If you encounter build failures at this stage, a recommended and more secure
# alternative is to perform the pull and save manually on a trusted host machine:
#
#   1. On a host with Docker access, manually pull the image using its immutable
#      digest. Choose the digest corresponding to your target architecture:
#
#      # For linux/amd64 (most common for servers and PCs):
#      docker pull redroid/redroid@sha256:d1ca0815eb68139a43d25a835e374559e9d18f5d5cea1a4288d4657c0074fb8d
#
#      # For linux/arm64 (Apple M-series, Raspberry Pi, AWS Graviton, etc.):
#      docker pull redroid/redroid@sha256:f070231146ba5043bdb225a1f51c77ef0765c1157131b26cb827078bf536c922
#
#   2. Then, save the pulled image to a tarball. Use the same digest as in step 1.
#      (Example for amd64):
#         docker save -o redroid.tar redroid/redroid@sha256:d1ca0815eb68139a43d25a835e374559e9d18f5d5cea1a4288d4657c0074fb8d
#
#   3. Place the resulting `redroid.tar` in the Docker build context (e.g., next to
#      this Dockerfile, in a path like `src/agentscope_runtime/sandbox/box/mobile/`).
#
#   4. Remove or skip this `redroid-fetcher` stage entirely, and in the final stage,
#      replace the line:
#         COPY --from=redroid-fetcher /redroid.tar /redroid.tar
#      with a direct copy from your build context:
#         COPY src/agentscope_runtime/sandbox/box/mobile/redroid.tar /redroid.tar
#
# This avoids running Docker-in-Docker and is more compatible with restricted build
# environments, while still maintaining supply chain security.

# Pin the redroid image to an immutable digest for security and reproducibility.
# The default digest is for the linux/amd64 architecture.
# To build for linux/arm64, pass the --build-arg flag to the docker build command:
# --build-arg REDROID_DIGEST=sha256:f070231146ba5043bdb225a1f51c77ef0765c1157131b26cb827078bf536c922
ARG REDROID_DIGEST=sha256:d1ca0815eb68139a43d25a835e374559e9d18f5d5cea1a4288d4657c0074fb8d

# --- Display a warning to the user before the privileged operation ---
RUN echo "" && \
    echo "========================================================================" && \
    echo "  >>> WARNING: Privileged Operation Ahead <<<" && \
    echo "========================================================================" && \
    echo "The following step will start a Docker-in-Docker (DinD) daemon." && \
    echo "This operation requires high privileges (e.g., the --privileged flag)" && \
    echo "and may fail in restricted environments like CI/CD pipelines." && \
    echo "" && \
    echo "  --- IF THIS STEP FAILS, USE THE ALTERNATIVE BELOW ---" && \
    echo "Manually 'docker pull' and 'docker save' the image to a .tar file, then" && \
    echo "copy it into the build context. For detailed instructions, please refer" && \
    echo "to the comments at the top of this stage in the Dockerfile:" && \
    echo "    src/agentscope_runtime/sandbox/box/mobile/Dockerfile" && \
    echo "========================================================================" && \
    echo ""

# --- Run the Docker-in-Docker process ---
RUN dockerd-entrypoint.sh & \
    TIMEOUT=30; \
    while ! docker info > /dev/null 2>&1; do \
        if [ $TIMEOUT -le 0 ]; then \
            echo "Docker daemon did not become ready in time." >&2; \
            exit 1; \
        fi; \
        sleep 1; \
        TIMEOUT=$((TIMEOUT - 1)); \
    done && \
    docker pull redroid/redroid@${REDROID_DIGEST} && \
    docker save -o /redroid.tar redroid/redroid@${REDROID_DIGEST}

# =================================================================
# Final Stage: Production Image
# =================================================================
FROM docker:28-dind

# 1. Install system dependencies
RUN apk update && \
    apk add --no-cache \
        bash nginx supervisor python3 py3-pip gettext coreutils \
        pngquant android-tools nginx-mod-http-lua \
        nodejs-lts

# 2. Install Python application
WORKDIR /app/python_app
COPY src/agentscope_runtime/sandbox/box/shared/ .
COPY src/agentscope_runtime/sandbox/box/mobile/box/requirements.txt .
RUN python3 -m venv .venv && \
    . .venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt && \
    rm requirements.txt

# 3. Copy the clean production package for adb-mcp
WORKDIR /app/node_app
COPY --from=node-builder /prod_bundle/ ./

# 4. Copy the clean production package for ws-scrcpy
WORKDIR /app/ws-scrcpy
COPY --from=ws-scrcpy-builder /prod_bundle/ ./

# 5. Copy configuration and startup scripts
WORKDIR /
COPY src/agentscope_runtime/sandbox/box/mobile/box/config/supervisord.conf.template /etc/supervisor/supervisord.conf.template
COPY src/agentscope_runtime/sandbox/box/mobile/box/config/nginx.conf.template /etc/nginx/nginx.conf.template
COPY src/agentscope_runtime/sandbox/box/mobile/box/mcp_server_configs.json /app/python_app/mcp_server_configs.json
COPY src/agentscope_runtime/sandbox/box/mobile/box/scripts/start.sh /start.sh
RUN chmod +x /start.sh

# 6. Copy the offline redroid image from the fetcher stage
COPY --from=redroid-fetcher /redroid.tar /redroid.tar

# 7. Set entrypoint
ENTRYPOINT ["/start.sh"]
