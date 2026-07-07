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
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

#
# -----------------------------------------------------------------------------
# Python packages
# -----------------------------------------------------------------------------
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip
RUN pip3 install \
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
   pillow


# -----------------------------------------------------------------------------
# OBS
# -----------------------------------------------------------------------------
RUN add-apt-repository ppa:obsproject/obs-studio && \
    apt update && \
    apt install obs-studio -y


# -----------------------------------------------------------------------------
# Working directory
# -----------------------------------------------------------------------------
WORKDIR /app

#COPY . /app

EXPOSE 8000

#CMD ["uvicorn", "telemetry_server:app", "--host", "0.0.0.0", "--port", "8000"]
