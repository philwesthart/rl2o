FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# -----------------------------------------------------------------------------
# Base packages
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    curl \
    wget \
    git \
    vim \
    nano \
    unzip \
    pkg-config \
    build-essential \
    cmake \
    gdb \
    sudo \
    iproute2 \
    net-tools \
    usbutils \
    pciutils \
    can-utils \
    ffmpeg \
    gstreamer1.0-tools \
    gstreamer1.0-libav \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    nginx \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-opencv \
    python3-numpy \
    python3-serial \
    python3-websockets \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Python packages
# -----------------------------------------------------------------------------
RUN pip3 install --break-system-packages \
    fastapi \
    uvicorn[standard] \
    python-can \
    cantools \
    aiofiles \
    jinja2 \
    websockets \
    pydantic \
    pyyaml \
    opencv-python \
    opencv-contrib-python \
    numpy \
    pillow

# -----------------------------------------------------------------------------
# Working directory
# -----------------------------------------------------------------------------
WORKDIR /app

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "telemetry_server:app", "--host", "0.0.0.0", "--port", "8000"]