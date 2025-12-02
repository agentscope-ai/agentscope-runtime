FROM alpine:latest AS downloader


ARG TARGET_IMAGE=redroid/redroid:11.0.0-240527

ARG OUTPUT_TAR=/tmp/redroid.tar

RUN apk update && \
    apk add --no-cache skopeo ca-certificates

RUN skopeo copy docker://${TARGET_IMAGE} docker-archive:${OUTPUT_TAR}

RUN ls -lh ${OUTPUT_TAR}

FROM docker:28-dind

RUN apk update && \
    apk add --no-cache \
        bash nginx supervisor python3 py3-pip gettext coreutils \
        nodejs-lts npm \
        build-base libpng-dev pngquant \
        android-tools


WORKDIR /app/python_app
COPY shared/ .
COPY mobile/box/requirements.txt .

RUN python3 -m venv .venv && \
    . .venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt


WORKDIR /app/node_app
COPY mobile/adbmcp/package*.json ./

RUN npm install

WORKDIR /app/node_app
COPY mobile/adbmcp/ .
RUN npm run build


WORKDIR /
COPY mobile/box/config/supervisord.conf.template /etc/supervisor/supervisord.conf.template
COPY mobile/box/config/nginx.conf /etc/nginx/nginx.conf
COPY mobile/box/mcp_server_configs.json /app/python_app/mcp_server_configs.json
COPY mobile/box/scripts/start.sh /start.sh
RUN chmod +x /start.sh

COPY --from=downloader /tmp/redroid.tar /redroid.tar

ENTRYPOINT ["/start.sh"]
