# Data Logger Service

This project installs a Python-based data logger as a systemd service on Ubuntu.

## Installation

1. Clone or copy the project:
   ```bash
   git clone <repo>
   cd data-logger

2. Run installer:

chmod +x install.sh
./install.sh

## Service Management

```
# Start
sudo systemctl start data_logger

# Stop
sudo systemctl stop data_logger

# Restart
sudo systemctl restart data_logger

# Status
sudo systemctl status data_logger
```


## Viewing Logs

```
# View logs
journalctl -u data_logger

# Follow logs live

journalctl -u data_logger -f

# Example log output
Apr 13 12:00:00 hostname data_logger[1234]: 2026-04-13 12:00:00 [INFO] Data Logger Service Started
Apr 13 12:00:05 hostname data_logger[1234]: 2026-04-13 12:00:05 [INFO] Sample data value: 42
```

## Log Retention Configuration

```

# Systemd journals are managed by journald. To configure log retention:
sudo nano /etc/systemd/journald.conf

# Key settings

# Limit total disk usage
SystemMaxUse=500M

# Keep logs for a time duration
MaxRetentionSec=7day

# After changes
sudo systemctl restart systemd-journald
```

## Manual Log Cleanup

```
# Clear logs older than 3 days
sudo journalctl --vacuum-time=3d

# Limit logs to 200MB
sudo journalctl --vacuum-size=200M
```





# Starting server
uvicorn telemetry_server:app
