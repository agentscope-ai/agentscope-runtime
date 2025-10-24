FROM node:22-slim

# Set ENV variables
ENV NODE_ENV=production
ENV WORKSPACE_DIR=/workspace

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --fix-missing \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    libssl-dev \
    git \
    supervisor \
    vim \
    nginx \
    gettext-base

WORKDIR /agentscope_runtime
RUN python3 -m venv venv
ENV PATH="/agentscope_runtime/venv/bin:$PATH"

# Copy application files
COPY src/agentscope_runtime/sandbox/box/shared/app.py ./
COPY src/agentscope_runtime/sandbox/box/shared/routers/ ./routers/
COPY src/agentscope_runtime/sandbox/box/shared/dependencies/ ./dependencies/
COPY src/agentscope_runtime/sandbox/box/shared/artifacts/ ./ext_services/artifacts/
COPY examples/custom_sandbox/box/third_party/markdownify-mcp/ ./mcp_project/markdownify-mcp/
COPY examples/custom_sandbox/box/third_party/steel-browser/ ./ext_services/steel-browser/
COPY examples/custom_sandbox/box/ ./

RUN pip install -r requirements.txt

# Install Google Chrome & fonts
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y --fix-missing google-chrome-stable \
    google-chrome-stable \
    fonts-wqy-zenhei \
    fonts-wqy-microhei

# Install steel browser
WORKDIR /agentscope_runtime/ext_services/steel-browser
RUN npm ci --omit=dev \
    && npm install -g webpack webpack-cli \
    && npm run build -w api \
    && rm -rf node_modules/.cache

# Install artifacts backend
WORKDIR /agentscope_runtime/ext_services/artifacts
RUN npm install \
    && rm -rf node_modules/.cache

# Install mcp_project/markdownify-mcp
WORKDIR /agentscope_runtime/mcp_project/markdownify-mcp
RUN npm install -g pnpm \
    && pnpm install \
    && pnpm run build \
    && rm -rf node_modules/.cache

WORKDIR ${WORKSPACE_DIR}
RUN mv /agentscope_runtime/config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN mv /agentscope_runtime/config/nginx.conf.template /etc/nginx/nginx.conf.template
RUN git init \
    && chmod +x /agentscope_runtime/scripts/start.sh

COPY .gitignore ${WORKSPACE_DIR}

# MCP required environment variables
ENV TAVILY_API_KEY=123
ENV AMAP_MAPS_API_KEY=123

# Cleanup to reduce image size
RUN pip cache purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && npm cache clean --force \
    && rm -rf ~/.npm/_cacache

CMD ["/bin/sh", "-c", "envsubst '$SECRET_TOKEN' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"]
