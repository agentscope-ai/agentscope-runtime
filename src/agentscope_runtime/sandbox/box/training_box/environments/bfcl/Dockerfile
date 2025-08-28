FROM node:22-slim

ENV NODE_ENV=production
ENV WORKSPACE_DIR=/workspace
ARG DEBIAN_FRONTEND=noninteractive

# Apt sources fix for Aliyun mirrors
RUN mkdir -p /etc/apt && touch /etc/apt/sources.list && \
    sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list

# Install base tools
RUN apt-get update && apt-get install -y \
    wget \
    bzip2 \
    ca-certificates \
    git \
    gcc \
    python3-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda matching architecture
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        MINICONDA=Miniconda3-latest-Linux-x86_64.sh; \
    elif [ "$ARCH" = "aarch64" ]; then \
        MINICONDA=Miniconda3-latest-Linux-aarch64.sh; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    wget https://repo.anaconda.com/miniconda/${MINICONDA} -O /tmp/miniconda.sh && \
    chmod +x /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

ENV PATH="/opt/conda/bin:${PATH}"

RUN conda init bash && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

WORKDIR /agentscope_runtime

# Create bfcl env
RUN conda create -n bfcl python=3.11.13 -y

# Copy project files
COPY src/agentscope_runtime/sandbox/box/training_box/ ./training_box/


# Install additional system deps if needed
RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*

# Clone gorilla and install into bfcl
RUN git clone https://github.com/ShishirPatil/gorilla.git && \
    conda run -n bfcl pip install ./gorilla/berkeley-function-call-leaderboard

# Install bfcl project requirements into bfcl (!!!)
RUN conda run -n bfcl pip install -r ./training_box/environments/bfcl/requirements.txt

RUN mkdir -p ./training_box/bfcl && \
    cp -r ./gorilla/berkeley-function-call-leaderboard/bfcl_eval/data ./training_box/bfcl/


# Process dataset inside bfcl env
WORKDIR /agentscope_runtime/training_box
# RUN conda run -n bfcl python ./environments/bf.cl/bfcl_dataprocess.py


# Environment variables
ENV PYTHONPATH=/agentscope_runtime:$PYTHONPATH
ENV ENV_PATH=/agentscope_runtime/training_box

ENV DATASET_NAME=$DATASET_SUB_TYPE

# Dynamically use DATASET_SUB_TYPE in the derived paths
ENV BFCL_DATA_PATH=${ENV_PATH}/bfcl/multi_turn/${DATASET_NAME}_processed.jsonl
ENV BFCL_SPLID_ID_PATH=${ENV_PATH}/bfcl/multi_turn/${DATASET_NAME}_split_ids.json


# Existing vars
ENV OPENAI_API_KEY=$OPENAI_API_KEY
ENV BFCL_ANSWER_PATH=${ENV_PATH}/bfcl/data/possible_answer

# Process dataset inside bfcl env
WORKDIR /agentscope_runtime/training_box
RUN conda run -n bfcl python ./environments/bfcl/bfcl_dataprocess.py

# Back to project root
WORKDIR /agentscope_runtime

# Ensure bfcl is active for any container command
ENTRYPOINT ["/bin/bash", "-c", ". /opt/conda/etc/profile.d/conda.sh && conda activate bfcl && exec \"$@\"", "--"]

# Default command
CMD ["bash", "training_box/bfcl.sh"]
