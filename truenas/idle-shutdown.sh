#!/bin/bash
# TrueNAS Idle Shutdown cron wrapper
# This script should be added to TrueNAS Scale Init/Shutdown Scripts or Cron Jobs.
# Recommended configuration: Run every 5 minutes as root.
# Example crontab entry:
# */5 * * * * /mnt/pool/truenas/idle-shutdown.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/truenas-idle-shutdown.log"

# Create log file if it doesn't exist
touch "$LOG_FILE" 2>/dev/null

# Execute the python shutdown check and log the output
/usr/bin/python3 "$SCRIPT_DIR/idle-shutdown.py" >> "$LOG_FILE" 2>&1
