#!/usr/bin/env python3
"""
scan_and_report.py
Automated OpenVAS / Greenbone scanner and Wazuh reporter.
1. Connects to local gvmd via unix socket.
2. Ensures Target and Task exist.
3. Triggers scan and monitors progress to completion.
4. Extracts vulnerabilities and formats for Wazuh.
5. Streams findings to Wazuh Manager via Syslog UDP 514 and writes to JSON log.
"""

import os
import sys
import time
import json
import socket
from datetime import datetime, timezone

from gvm.connections import UnixSocketConnection
from gvm.protocols.gmp import Gmp
from gvm.transforms import EtreeTransform
from gvm.protocols.gmp.requests.v224._targets import AliveTest

# Configuration from environment
SOCKET_PATH = os.environ.get("SOCKET_PATH", "/run/gvmd/gvmd.sock")
GMP_USER = os.environ.get("GMP_USER", "admin")
GMP_PASSWORD = os.environ.get("GMP_PASSWORD", "admin")

TARGET_NAME = os.environ.get("TARGET_NAME", "Home Network (192.168.0.0/24)")
TARGET_HOSTS = os.environ.get("TARGET_HOSTS", "192.168.0.0/24").split(",")
TASK_NAME = os.environ.get("TASK_NAME", "Automated Boot Vulnerability Scan")

# Configs & Port lists (defaults from Greenbone feed)
SCAN_CONFIG_ID = os.environ.get("SCAN_CONFIG_ID", "daba56c8-73ec-11df-a475-002264764cea")  # Full and fast
SCANNER_ID = os.environ.get("SCANNER_ID", "08b69003-5fc2-4037-a479-93b440211c73")          # OpenVAS Default
PORT_LIST_ID = os.environ.get("PORT_LIST_ID", "33d0cd82-57c6-11e1-8ed1-406186ea4fc5")      # All IANA TCP

WAZUH_SYSLOG_HOST = os.environ.get("WAZUH_SYSLOG_HOST", "192.168.0.248")
WAZUH_SYSLOG_PORT = int(os.environ.get("WAZUH_SYSLOG_PORT", "514"))
REPORT_OUTPUT_FILE = os.environ.get("REPORT_OUTPUT_FILE", "/var/log/openvas_report.json")
MIN_SEVERITY = os.environ.get("MIN_SEVERITY", "LOW").upper()

SEVERITY_LEVELS = ["LOG", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
MIN_SEV_IDX = SEVERITY_LEVELS.index(MIN_SEVERITY) if MIN_SEVERITY in SEVERITY_LEVELS else 1
SYSLOG_PRI = "<141>"  # local1.notice


def wait_for_gvmd(path, max_attempts=40, delay=10):
    print(f"[INFO] Waiting for gvmd socket at {path}...")
    for i in range(max_attempts):
        if os.path.exists(path):
            try:
                conn = UnixSocketConnection(path=path)
                with Gmp(connection=conn, transform=EtreeTransform()) as gmp:
                    gmp.authenticate(GMP_USER, GMP_PASSWORD)
                    ver = gmp.get_version()
                    print(f"[INFO] Connected to gvmd version: {ver.findtext('version')}")
                    return True
            except Exception as e:
                print(f"[DEBUG] Socket exists but gvmd not ready yet ({e}). Waiting...")
        time.sleep(delay)
    return False


def get_or_create_target(gmp):
    targets = gmp.get_targets(filter_string=f'name="{TARGET_NAME}"')
    existing = targets.xpath('target')
    if existing:
        target_id = existing[0].get('id')
        print(f"[INFO] Using existing target: {TARGET_NAME} (ID: {target_id})")
        return target_id

    print(f"[INFO] Creating target: {TARGET_NAME} with hosts {TARGET_HOSTS}")
    res = gmp.create_target(
        name=TARGET_NAME,
        hosts=TARGET_HOSTS,
        comment="Automated LAN scan target",
        alive_test=AliveTest.ICMP_TCP_ACK_SERVICE_AND_ARP_PING,
        port_list_id=PORT_LIST_ID
    )
    target_id = res.get('id')
    print(f"[INFO] Target created: {target_id}")
    return target_id


def get_or_create_task(gmp, target_id):
    tasks = gmp.get_tasks(filter_string=f'name="{TASK_NAME}"')
    existing = tasks.xpath('task')
    if existing:
        task_id = existing[0].get('id')
        print(f"[INFO] Using existing task: {TASK_NAME} (ID: {task_id})")
        return task_id

    print(f"[INFO] Creating task: {TASK_NAME}")
    res = gmp.create_task(
        name=TASK_NAME,
        config_id=SCAN_CONFIG_ID,
        target_id=target_id,
        scanner_id=SCANNER_ID,
        comment="Automated Boot Vulnerability Scan"
    )
    task_id = res.get('id')
    print(f"[INFO] Task created: {task_id}")
    return task_id


def run_scan(gmp, task_id):
    print(f"[INFO] Triggering scan for task: {task_id}")
    res = gmp.start_task(task_id)
    report_id = res.findtext('report_id')
    print(f"[INFO] Scan initiated. Report ID: {report_id}")

    # Poll status
    while True:
        time.sleep(20)
        task = gmp.get_task(task_id)
        status = task.xpath('task/status')[0].text
        progress = task.xpath('task/progress')[0].text if task.xpath('task/progress') else "0"
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{timestamp}] Scan status: {status} ({progress}%)")

        if status in ["Done", "Stopped"]:
            print(f"[INFO] Scan finished with status: {status}")
            break
        elif status in ["Internal Error", "Interrupted"]:
            print(f"[ERROR] Scan failed with status: {status}")
            sys.exit(1)

    return report_id


def map_severity(threat_text, score_float):
    t = (threat_text or "").upper()
    if t in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        return t
    if score_float >= 9.0:
        return "CRITICAL"
    elif score_float >= 7.0:
        return "HIGH"
    elif score_float >= 4.0:
        return "MEDIUM"
    elif score_float > 0.0:
        return "LOW"
    return "LOG"


def process_and_send_findings(gmp, report_id):
    print(f"[INFO] Fetching full report details for: {report_id}")
    report_xml = gmp.get_report(report_id, details=True, ignore_pagination=True)
    results = report_xml.xpath('.//results/result')
    print(f"[INFO] Total results in scan report: {len(results)}")

    syslog_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "LOG": 0}
    sent_count = 0

    # Ensure log directory exists
    log_dir = os.path.dirname(REPORT_OUTPUT_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    with open(REPORT_OUTPUT_FILE, "a") as log_file:
        for r in results:
            name = r.findtext('name') or 'Unnamed Finding'
            host = r.findtext('host') or 'unknown'
            port = r.findtext('port') or 'unknown'
            threat = r.findtext('threat') or 'Log'
            severity_text = r.findtext('severity') or '0'
            try:
                score = float(severity_text)
            except ValueError:
                score = 0.0

            sev_label = map_severity(threat, score)
            counts[sev_label] = counts.get(sev_label, 0) + 1

            sev_idx = SEVERITY_LEVELS.index(sev_label) if sev_label in SEVERITY_LEVELS else 0
            if sev_idx < MIN_SEV_IDX:
                continue

            desc = (r.findtext('description') or '').strip()
            # Clean / truncate description for syslog
            if len(desc) > 300:
                desc = desc[:300] + "..."

            cve = r.findtext('.//nvt/cve') or 'N/A'
            solution = (r.findtext('.//nvt/solution') or '').strip()
            if len(solution) > 200:
                solution = solution[:200] + "..."

            event = {
                "integration": "openvas",
                "severity": sev_label,
                "title": name,
                "host": host,
                "target_port": port,
                "cvss_score": score,
                "cve": cve,
                "solution": solution,
                "description": desc,
                "scan_time": datetime.now(timezone.utc).isoformat(),
                "report_id": report_id,
            }

            event_json = json.dumps(event)

            # 1. Send via Syslog UDP to Wazuh Manager
            now_syslog = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
            syslog_msg = f"{SYSLOG_PRI}{now_syslog} openvas: {event_json}".encode("utf-8")
            try:
                syslog_sock.sendto(syslog_msg, (WAZUH_SYSLOG_HOST, WAZUH_SYSLOG_PORT))
                sent_count += 1
                if sent_count % 50 == 0:
                    time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Failed to send syslog packet: {e}")

            # 2. Write to local report log
            log_file.write(event_json + "\n")

    syslog_sock.close()
    print(f"[INFO] Summary of findings: {counts}")
    print(f"[INFO] Successfully forwarded {sent_count} findings ({MIN_SEVERITY}+) to Wazuh ({WAZUH_SYSLOG_HOST}:{WAZUH_SYSLOG_PORT})")
    print(f"[INFO] Report appended to {REPORT_OUTPUT_FILE}")
    return sent_count


def main():
    print("=======================================================")
    print("OpenVAS Automated Boot Scan & Wazuh Reporter")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: {TARGET_NAME} ({TARGET_HOSTS})")
    print(f"Wazuh Syslog: {WAZUH_SYSLOG_HOST}:{WAZUH_SYSLOG_PORT}")
    print("=======================================================")

    if not wait_for_gvmd(SOCKET_PATH):
        print("[FATAL] gvmd was not reachable within the timeout period. Exiting.")
        sys.exit(1)

    connection = UnixSocketConnection(path=SOCKET_PATH)
    transform = EtreeTransform()

    with Gmp(connection=connection, transform=transform) as gmp:
        gmp.authenticate(GMP_USER, GMP_PASSWORD)
        target_id = get_or_create_target(gmp)
        task_id = get_or_create_task(gmp, target_id)
        report_id = run_scan(gmp, task_id)
        process_and_send_findings(gmp, report_id)

    print("[INFO] OpenVAS scan workflow completed successfully.")


if __name__ == "__main__":
    main()
