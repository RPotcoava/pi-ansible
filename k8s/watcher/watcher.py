import os
import time
import socket
import struct
import subprocess

# Configurations from environment variables
TRUENAS_IP = os.getenv("TRUENAS_IP", "192.168.0.15")
TRUENAS_MAC = os.getenv("TRUENAS_MAC", "AA:BB:CC:DD:EE:FF") # Replace with actual MAC address
REDIS_HOST = os.getenv("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CONSUME_DIR = os.getenv("CONSUME_DIR", "/paperless-consume")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))

def is_truenas_online(ip):
    """Checks if the TrueNAS server is online using ping."""
    try:
        # Ping with 1 packet and 1 second timeout
        output = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return output.returncode == 0
    except Exception as e:
        print(f"Error pinging {ip}: {e}")
        return False

def send_wol(mac_address):
    """Sends a Wake-on-LAN magic packet to the specified MAC address."""
    print(f"Sending Wake-on-LAN magic packet to {mac_address}...")
    try:
        clean_mac = mac_address.replace(":", "").replace("-", "")
        if len(clean_mac) != 12:
            raise ValueError("MAC address must be 12 hexadecimal characters")
        
        # Hexadecimal string to bytes
        mac_bytes = bytes.fromhex(clean_mac)
        
        # Create magic packet payload: 6 bytes of 0xFF followed by 16 repetitions of MAC
        payload = b'\xff' * 6 + mac_bytes * 16
        
        # Send UDP broadcast
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Broadcast on port 9 (default WoL port)
            s.sendto(payload, ("255.255.255.255", 9))
        print("WoL magic packet sent successfully.")
    except Exception as e:
        print(f"Failed to send WoL packet: {e}")

def check_paperless_consume(directory):
    """Checks if there are files in the Paperless consume folder."""
    if not os.path.exists(directory):
        return False
    try:
        # Check if directory has files (excluding hidden files)
        files = [f for f in os.listdir(directory) if not f.startswith(".")]
        if files:
            print(f"Paperless consume folder contains {len(files)} files: {files}")
            return True
    except Exception as e:
        print(f"Error reading directory {directory}: {e}")
    return False

def check_redis_queues(host, port):
    """Checks if there are active or waiting jobs in Redis for Immich/Paperless."""
    try:
        # Connect to Redis via socket to avoid external dependencies like redis-py
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((host, port))
        
        # Send REDIS 'KEYS' command to look for pending job queues
        # Immich uses BullMQ which prefixes keys with 'bull:'
        # Paperless-ngx uses django-q/celery which might store in celery/default keys
        # We will request all keys and inspect if they match queue prefixes
        s.sendall(b"*2\r\n$4\r\nKEYS\r\n$6\r\nbull:*\r\n")
        response = s.recv(4096)
        s.close()
        
        # If we find key patterns related to wait/active states, tasks are queued
        if b"wait" in response or b"active" in response:
            print("Detected active or waiting jobs in Redis.")
            return True
    except Exception as e:
        # Redis might not be reachable or empty, log and fail gracefully
        print(f"Redis check status: {e}")
    return False

def main():
    print("DMS Wake-on-LAN Watcher started.")
    print(f"Monitoring: {CONSUME_DIR} and Redis ({REDIS_HOST}:{REDIS_PORT})")
    print(f"TrueNAS Target: {TRUENAS_IP} (MAC: {TRUENAS_MAC})")
    
    while True:
        try:
            tasks_pending = False
            
            # Check Paperless consume directory
            if check_paperless_consume(CONSUME_DIR):
                tasks_pending = True
                
            # Check Redis queues if no local files but maybe jobs in database/Redis
            if not tasks_pending and check_redis_queues(REDIS_HOST, REDIS_PORT):
                tasks_pending = True
                
            if tasks_pending:
                print("Pending tasks detected. Checking TrueNAS power state...")
                if not is_truenas_online(TRUENAS_IP):
                    print("TrueNAS is offline. Triggering Wake-on-LAN...")
                    send_wol(TRUENAS_MAC)
                else:
                    print("TrueNAS is already online. Waiting for processing to start/continue.")
            else:
                print("No pending tasks. TrueNAS can remain in current state.")
                
        except Exception as e:
            print(f"Error in watcher loop: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
