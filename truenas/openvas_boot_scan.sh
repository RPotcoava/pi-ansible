#!/bin/bash
# /mnt/SSD/scripts/openvas/openvas_boot_scan.sh
# Automated OpenVAS boot scanner trigger, reporter, and auto-shutdown coordinator

SCRIPT_DIR="/mnt/SSD/scripts/openvas"
CONF_FILE="${SCRIPT_DIR}/openvas_scan.conf"

if [ -f "${CONF_FILE}" ]; then
    source "${CONF_FILE}"
fi

# Defaults
TARGET_NAME="${TARGET_NAME:-Home Network (192.168.0.0/24)}"
TARGET_HOSTS="${TARGET_HOSTS:-192.168.0.0/24}"
TASK_NAME="${TASK_NAME:-Automated Boot Vulnerability Scan}"
SCAN_CONFIG_ID="${SCAN_CONFIG_ID:-daba56c8-73ec-11df-a475-002264764cea}"
SCANNER_ID="${SCANNER_ID:-08b69003-5fc2-4037-a479-93b440211c73}"
PORT_LIST_ID="${PORT_LIST_ID:-33d0cd82-57c6-11e1-8ed1-406186ea4fc5}"
WAZUH_SYSLOG_HOST="${WAZUH_SYSLOG_HOST:-192.168.0.248}"
WAZUH_SYSLOG_PORT="${WAZUH_SYSLOG_PORT:-514}"
REPORT_OUTPUT_FILE="${REPORT_OUTPUT_FILE:-/var/log/openvas_report.json}"
MIN_SEVERITY="${MIN_SEVERITY:-LOW}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-true}"
SHUTDOWN_GRACE_SECONDS="${SHUTDOWN_GRACE_SECONDS:-60}"
CANCEL_FILE="${CANCEL_FILE:-/tmp/cancel_shutdown}"
DISABLE_SCAN_FILE="${DISABLE_SCAN_FILE:-/tmp/disable_openvas_scan}"

SOCKET_DIR="/mnt/.ix-apps/docker/volumes/ix-greenbone-ce_gvmd_socket_vol/_data"
SOCKET_FILE="${SOCKET_DIR}/gvmd.sock"

echo "=========================================================="
echo "Starting OpenVAS Boot Scan Coordinator: $(date -u)"
echo "Target: ${TARGET_NAME} (${TARGET_HOSTS})"
echo "Wazuh Destination: ${WAZUH_SYSLOG_HOST}:${WAZUH_SYSLOG_PORT}"
echo "=========================================================="

# Check disable scan flag
if [ -f "${DISABLE_SCAN_FILE}" ]; then
    echo "[INFO] Scan disabled via ${DISABLE_SCAN_FILE}. Exiting."
    exit 0
fi

# 1. Wait for Docker daemon to become responsive
echo "[INFO] Waiting for Docker daemon..."
MAX_WAIT=120
while ! docker info >/dev/null 2>&1; do
    sleep 5
    MAX_WAIT=$((MAX_WAIT - 5))
    if [ ${MAX_WAIT} -le 0 ]; then
        echo "[ERROR] Docker did not become available in time. Exiting."
        exit 1
    fi
done
echo "[INFO] Docker daemon is ready."

# 2. Wait for Greenbone gvmd & ospd containers to be up
echo "[INFO] Waiting for Greenbone containers to be running..."
MAX_CONTAINER_WAIT=300
while true; do
    GVMD_STATUS=$(docker inspect -f '{{.State.Status}}' ix-greenbone-ce-gvmd-1 2>/dev/null || echo "not_found")
    OSPD_STATUS=$(docker inspect -f '{{.State.Status}}' ix-greenbone-ce-ospd-openvas-1 2>/dev/null || echo "not_found")

    if [ "${GVMD_STATUS}" = "running" ] && [ "${OSPD_STATUS}" = "running" ] && [ -S "${SOCKET_FILE}" ]; then
        echo "[INFO] Greenbone containers and socket are ready."
        break
    fi

    sleep 10
    MAX_CONTAINER_WAIT=$((MAX_CONTAINER_WAIT - 10))
    if [ ${MAX_CONTAINER_WAIT} -le 0 ]; then
        echo "[ERROR] Greenbone containers did not become ready within timeout. Exiting."
        exit 1
    fi
done

touch "${REPORT_OUTPUT_FILE}" && chmod 666 "${REPORT_OUTPUT_FILE}"

echo "[INFO] Launching scan_and_report.py..."
docker run --rm \
    -u root \
    --net host \
    -v "${SOCKET_DIR}/gvmd.sock:/run/gvmd/gvmd.sock" \
    -v "${SCRIPT_DIR}:/scripts" \
    -v /var/log:/var/log \
    -e TARGET_NAME="${TARGET_NAME}" \
    -e TARGET_HOSTS="${TARGET_HOSTS}" \
    -e TASK_NAME="${TASK_NAME}" \
    -e SCAN_CONFIG_ID="${SCAN_CONFIG_ID}" \
    -e SCANNER_ID="${SCANNER_ID}" \
    -e PORT_LIST_ID="${PORT_LIST_ID}" \
    -e WAZUH_SYSLOG_HOST="${WAZUH_SYSLOG_HOST}" \
    -e WAZUH_SYSLOG_PORT="${WAZUH_SYSLOG_PORT}" \
    -e REPORT_OUTPUT_FILE="${REPORT_OUTPUT_FILE}" \
    -e MIN_SEVERITY="${MIN_SEVERITY}" \
    registry.community.greenbone.net/community/gvm-tools:latest \
    python3 /scripts/openvas_scan_and_report.py

SCAN_EXIT_CODE=$?
echo "[INFO] openvas_scan_and_report.py finished with exit code: ${SCAN_EXIT_CODE}"

if [ ${SCAN_EXIT_CODE} -ne 0 ]; then
    echo "[WARN] Scan did not complete cleanly (code: ${SCAN_EXIT_CODE}). Skipping shutdown for investigation."
    exit ${SCAN_EXIT_CODE}
fi

# 4. Check if auto shutdown is desired
if [ "${AUTO_SHUTDOWN}" != "true" ]; then
    echo "[INFO] AUTO_SHUTDOWN is disabled in ${CONF_FILE}. Server will remain powered on."
    exit 0
fi

# 5. Check if an active interactive SSH session exists (safety guard)
if who | grep -q 'pts/'; then
    echo "[WARN] Active interactive SSH session detected. Aborting automated poweroff to protect user session."
    exit 0
fi

# 6. Grace period before shutdown (allow user to cancel)
echo "[INFO] Scan and Wazuh reporting complete. Preparing for shutdown in ${SHUTDOWN_GRACE_SECONDS} seconds."
echo "[INFO] To cancel shutdown, run: touch ${CANCEL_FILE}"

REMAINING=${SHUTDOWN_GRACE_SECONDS}
while [ ${REMAINING} -gt 0 ]; do
    if [ -f "${CANCEL_FILE}" ]; then
        echo "[INFO] Shutdown cancelled via ${CANCEL_FILE}."
        rm -f "${CANCEL_FILE}"
        exit 0
    fi
    if [ -f "/tmp/disable_auto_shutdown" ]; then
        echo "[INFO] Shutdown cancelled via /tmp/disable_auto_shutdown."
        exit 0
    fi
    if who | grep -q 'pts/'; then
        echo "[INFO] User logged in during grace period. Cancelling shutdown."
        exit 0
    fi
    sleep 5
    REMAINING=$((REMAINING - 5))
    echo "[INFO] Shutting down in ${REMAINING}s..."
done

echo "[INFO] Grace period expired. Powering off TrueNAS..."
/sbin/poweroff
