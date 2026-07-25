#!/bin/bash

# Ensure we have an SSH key
if [ ! -f ~/.ssh/id_ed25519 ]; then
    echo "No SSH key found at ~/.ssh/id_ed25519. Generating one..."
    ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
fi

# Ask for the 'razvan' user password
echo -n "Enter the SSH password for user 'razvan' on your Raspberry Pis: "
read -s PASSWORD
echo ""

IPS=("192.168.0.53" "192.168.0.21" "192.168.0.14" "192.168.0.101")

for IP in "${IPS[@]}"; do
    echo "========================================"
    echo "Processing node: $IP"
    echo "========================================"

    # Step 1: Repair home folder permissions using expect (if owned by root)
    echo "Repairing folder permissions for user 'razvan' on $IP..."
    expect -c "
        spawn ssh -o StrictHostKeyChecking=no razvan@$IP \"echo '$PASSWORD' | sudo -S chown -R razvan:razvan /home/razvan && echo '$PASSWORD' | sudo -S mkdir -p /home/razvan/.ssh && echo '$PASSWORD' | sudo -S chown razvan:razvan /home/razvan/.ssh && echo '$PASSWORD' | sudo -S chmod 700 /home/razvan/.ssh || true\"
        expect {
            \"*password:*\" {
                send \"$PASSWORD\r\"
                exp_continue
            }
            eof
        }
    "

    # Step 2: Use expect to copy the SSH key using password
    echo "Copying SSH public key to $IP..."
    expect -c "
        spawn ssh-copy-id -o StrictHostKeyChecking=no razvan@$IP
        expect {
            \"*password:*\" {
                send \"$PASSWORD\r\"
                exp_continue
            }
            eof
        }
    "

    # Verify key-based access works
    echo "Testing passwordless SSH connection to $IP..."
    ssh -o BatchMode=yes -o ConnectTimeout=3 razvan@$IP "echo 'SSH Connection Successful!'"
    if [ $? -eq 0 ]; then
        echo "Installing Wazuh Agent on $IP..."
        # Pass the password to remote bash to use for sudo -S
        ssh razvan@$IP "export PASS=\"$PASSWORD\"; bash -s" <<'ENDSSH'
            # Check if agent is already installed
            if systemctl is-active --quiet wazuh-agent 2>/dev/null; then
                echo "Wazuh Agent is already installed and running."
                exit 0
            fi

            echo "Elevating privileges using sudo..."

            # Install dependencies
            echo "$PASS" | sudo -S apt-get update
            echo "$PASS" | sudo -S apt-get install -y curl apt-transport-https lsb-release gnupg

            # Add repository keys
            curl -sL https://packages.wazuh.com/key/GPG-KEY-WAZUH -o /tmp/wazuh.gpg
            echo "$PASS" | sudo -S gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import /tmp/wazuh.gpg
            echo "$PASS" | sudo -S chmod 644 /usr/share/keyrings/wazuh.gpg
            rm -f /tmp/wazuh.gpg

            # Register repo
            echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" > /tmp/wazuh.list
            echo "$PASS" | sudo -S mv /tmp/wazuh.list /etc/apt/sources.list.d/wazuh.list

            # Install and configure
            echo "$PASS" | sudo -S apt-get update
            echo "$PASS" | sudo -S env WAZUH_MANAGER='192.168.0.248' apt-get install wazuh-agent -y

            # Start service
            echo "$PASS" | sudo -S systemctl daemon-reload
            echo "$PASS" | sudo -S systemctl enable wazuh-agent
            echo "$PASS" | sudo -S systemctl start wazuh-agent
            echo "Wazuh Agent installation complete!"
ENDSSH
    else
        echo "Failed to establish key-based SSH connection to $IP. Skipping installation."
    fi
done
