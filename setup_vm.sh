#!/usr/bin/env bash
set -euo pipefail

echo "=== 1. Installing system packages (ffmpeg, python3-venv, sqlite3) ==="
sudo apt-get update
sudo apt-get install -y ffmpeg python3-venv python3-pip sqlite3

echo "=== 2. Configuring 2GB Swap File (prevents Out-Of-Memory during MoviePy rendering on e2-micro) ==="
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap file created and enabled."
else
    echo "Swap file already exists."
fi

echo "=== 3. Setting up Python virtual environment & dependencies ==="
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${APP_DIR}"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "=== 4. Initializing SQLite Database (studio.db) ==="
.venv/bin/python database.py
mkdir -p output

echo "=== 5. Creating systemd service for 24/7 Streamlit Dashboard ==="
SERVICE_FILE="/etc/systemd/system/youtube-studio.service"
sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Automated YouTube Content Studio Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/streamlit run ${APP_DIR}/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable youtube-studio.service
sudo systemctl restart youtube-studio.service

EXTERNAL_IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip || echo "<VM_EXTERNAL_IP>")
echo ""
echo "=================================================================="
echo "✅ Setup Complete!"
echo "Dashboard URL: http://${EXTERNAL_IP}:8501"
echo "Check service logs: sudo journalctl -u youtube-studio -f"
echo "=================================================================="
