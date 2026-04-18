#!/bin/bash

set -e

SERVICE_NAME="data_logger"
INSTALL_DIR="/opt/data-logger"

echo "Creating install directory..."
sudo mkdir -p $INSTALL_DIR

echo "Copying files..."
sudo cp data_logger.py $INSTALL_DIR/
sudo chmod +x $INSTALL_DIR/data_logger.py

echo "Installing systemd service..."
sudo cp data_logger.service /etc/systemd/system/${SERVICE_NAME}.service

echo "Reloading systemd..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

echo "Enabling service..."
sudo systemctl enable ${SERVICE_NAME}.service

echo "Starting service..."
sudo systemctl start ${SERVICE_NAME}.service

echo "Installation complete!"
echo "Check logs with:"
echo "  journalctl -u ${SERVICE_NAME} -f"