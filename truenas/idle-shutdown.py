import os
import time
import socket
import subprocess

# Paths on TrueNAS
ENV_FILE = "/mnt/pool/truenas/.env" # Path to your .env file on TrueNAS
CONSUME_DIR = "/mnt/pool/paperless/consume"
IDLE_STATE_FILE = "/tmp/truenas_idle_since"
MAX_IDLE_TIME = 1800 # 30 minutes in seconds

def get_k8s_redis_ip():
    """Reads K8S_REDIS_IP from the local .env file."""
    if not os.path.exists(ENV_FILE):
        # Fallback to checking typical location
        local_env = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(local_env):
            ENV_FILE = local_env
        else:
            return None
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.startswith("K8S_REDIS_IP="):
                    return line.split("=")[1].strip()
    except Exception as e:
        print(f"Error reading .env file: {e}")
    return None

def has_pending_tasks(redis_ip, consume_dir):
    """Checks if there are files in the consume folder or tasks in Redis."""
    # 1. Check Paperless consume directory
    if os.path.exists(consume_dir):
        try:
            files = [f for f in os.listdir(consume_dir) if not f.startswith(".")]
            if files:
                print(f"Active tasks: {len(files)} files in consume directory.")
                return True
        except Exception as e:
            print(f"Error checking consume dir: {e}")

    # 2. Check Redis queues
    if redis_ip:
        try:
            # Query Redis via raw socket to check BullMQ keys
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((redis_ip, 6379))
            s.sendall(b"*2\r\n$4\r\nKEYS\r\n$6\r\nbull:*\r\n")
            response = s.recv(4096)
            s.close()
            # If wait or active states are in the Redis response, we have queued tasks
            if b"wait" in response or b"active" in response:
                print("Active tasks: Pending jobs detected in Redis queues.")
                return True
        except Exception as e:
            print(f"Error querying Redis at {redis_ip}: {e}")
            
    return False

def shutdown_system():
    """Powers off the TrueNAS Scale host."""
    print("Initiating system shutdown...")
    try:
        subprocess.run(["sudo", "/sbin/poweroff"])
    except Exception as e:
        print(f"Failed to execute shutdown command: {e}")

def main():
    redis_ip = get_k8s_redis_ip()
    print(f"Checking system status. Redis IP: {redis_ip}, Consume Dir: {CONSUME_DIR}")
    
    if has_pending_tasks(redis_ip, CONSUME_DIR):
        # Reset idle timer if active tasks exist
        if os.path.exists(IDLE_STATE_FILE):
            os.remove(IDLE_STATE_FILE)
            print("Reset idle state file due to active tasks.")
        print("System is busy. Postponing shutdown.")
    else:
        # System is idle
        now = time.time()
        if not os.path.exists(IDLE_STATE_FILE):
            # Write start of idle state
            with open(IDLE_STATE_FILE, "w") as f:
                f.write(str(now))
            print(f"System became idle. Started idle timer.")
        else:
            # Read start of idle state
            try:
                with open(IDLE_STATE_FILE, "r") as f:
                    idle_since = float(f.read().strip())
                idle_duration = now - idle_since
                print(f"System has been idle for {int(idle_duration)} seconds.")
                
                if idle_duration >= MAX_IDLE_TIME:
                    # Clean up file and shutdown
                    os.remove(IDLE_STATE_FILE)
                    shutdown_system()
                else:
                    remaining = int(MAX_IDLE_TIME - idle_duration)
                    print(f"Shutting down in {remaining} seconds if idle state continues.")
            except Exception as e:
                print(f"Error processing idle state file: {e}")
                # Reset state file just in case of corruption
                os.remove(IDLE_STATE_FILE)

if __name__ == "__main__":
    main()
