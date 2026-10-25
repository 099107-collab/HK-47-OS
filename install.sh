#!/usr/bin/env bash
# =============================================================================
# HK-47 OS :: Automated Provisioning & Installation Script
# Target: Pocket CHIP (Allwinner R8, ARMhf, Debian Buster) / Any Linux Host
# =============================================================================
set -e

# Visual banner
cat << 'EOF'
  [== HK-47 TACTICAL OS ==]
  / ===================== \
 |   (o)             (o)   |
 |          =====          |
  \        \_____/        /
   \_____________________/
  "Statement: Commencing installation, meatbag."
EOF

echo ""
echo "[*] Verifying execution privileges..."
if [ "$EUID" -ne 0 ]; then
    echo "Correction: You must run this installer as root (or with sudo), meatbag."
    exit 1
fi

TARGET_USER="${SUDO_USER:-chip}"
TARGET_HOME=$(eval echo "~$TARGET_USER")
INSTALL_DIR="/opt/hk47_os"

echo "[*] Target user: $TARGET_USER (home: $TARGET_HOME)"

# -----------------------------------------------------------------------------
# 1. System Clock & SSL Certificate Fixes
# -----------------------------------------------------------------------------
CURRENT_YEAR=$(date +%Y 2>/dev/null || echo 1970)
if [ "$CURRENT_YEAR" -lt 2024 ]; then
    echo "[*] System clock is skewed ($CURRENT_YEAR) due to missing RTC battery. Synchronizing..."
    HTTP_DATE=$(curl -sI -k https://www.google.com 2>/dev/null | grep -i '^date:' | cut -d' ' -f2- || true)
    if [ -n "$HTTP_DATE" ]; then
        date -s "$HTTP_DATE" 2>/dev/null || true
        echo "[+] System clock synchronized to: $(date)"
    fi
fi

echo "[*] Updating package index and installing system prerequisites..."

# Avoid checking validity date on archived Debian distributions
apt-get update -o Acquire::Check-Valid-Until=false -y 2>/dev/null || apt-get update -y || true

# Reinstall/update CA certs to resolve TLS trust issues
apt-get install -y --reinstall ca-certificates 2>/dev/null || true
update-ca-certificates 2>/dev/null || true

DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    espeak \
    bluez \
    python3-evdev \
    python3-cryptography \
    git \
    portaudio19-dev \
    python3-serial \
    i2c-tools \
    spi-tools \
    rfkill \
    network-manager \
    alsa-utils \
    tar \
    curl || true

# Optional hardware libraries (non-fatal if absent on generic hosts)
pip3 install spidev RPi.GPIO 2>/dev/null || true

# -----------------------------------------------------------------------------
# 2. Staging HK-47 OS Codebase
# -----------------------------------------------------------------------------
echo "[*] Staging HK-47 OS files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

if [ -f "$SCRIPT_DIR/main.py" ]; then
    echo "[*] Copying local files from $SCRIPT_DIR..."
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
else
    echo "[*] Standalone execution detected. Fetching complete repository from GitHub..."
    curl -k -sSL https://github.com/099107-collab/HK-47-OS/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 -C "$INSTALL_DIR" || {
        echo "[*] Fallback: Cloning repository via git..."
        GIT_SSL_NO_VERIFY=true git clone https://github.com/099107-collab/HK-47-OS.git "$INSTALL_DIR"
    }
fi

# -----------------------------------------------------------------------------
# 3. Python Virtual Environment & Dependencies
# -----------------------------------------------------------------------------
echo "[*] Creating dedicated Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"

echo "[*] Installing Python dependencies into venv..."
"$INSTALL_DIR/venv/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade pip 2>/dev/null || true
"$INSTALL_DIR/venv/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    openai rich urwid pyserial cryptography spidev 2>/dev/null || \
    "$INSTALL_DIR/venv/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    openai rich urwid pyserial cryptography

echo "[*] Setting up HK-47 directory in user home: $TARGET_HOME/.hk47..."
mkdir -p "$TARGET_HOME/.hk47"
chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.hk47"

# -----------------------------------------------------------------------------
# 4. API Key Registration
# -----------------------------------------------------------------------------
if [ -z "$OPENAI_API_KEY" ]; then
    echo ""
    echo "Query: Enter your OpenAI API Key for HK-47 neural uplink (leave blank to skip): "
    if [ -t 0 ]; then
        read -r -s INPUT_KEY
    elif [ -c /dev/tty ]; then
        read -r -s INPUT_KEY < /dev/tty
    else
        INPUT_KEY=""
    fi
    echo ""
    OPENAI_API_KEY="$INPUT_KEY"
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo "OPENAI_API_KEY=$OPENAI_API_KEY" > "$INSTALL_DIR/.env"
    echo "$OPENAI_API_KEY" > "$TARGET_HOME/.hk47/api_key"
    chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.hk47/api_key"
    chmod 600 "$TARGET_HOME/.hk47/api_key"
    chmod 600 "$INSTALL_DIR/.env"
    echo "[+] Uplink key securely registered."
else
    touch "$INSTALL_DIR/.env"
    echo "[!] No API key provided. HK-47 will operate in offline heuristic mode."
fi

# Ensure correct file permissions
chown -R "$TARGET_USER:$TARGET_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/install.sh"

# -----------------------------------------------------------------------------
# 5. Systemd Service Deployment
# -----------------------------------------------------------------------------
echo "[*] Installing systemd service: hk47-os.service..."
cat << EOF > /etc/systemd/system/hk47-os.service
[Unit]
Description=HK-47 AI Operating System
After=network.target

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=-$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py
Restart=on-failure
StandardInput=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable hk47-os.service || true

echo ""
echo "================================================================="
echo "Conclusion: Installation complete, meatbag. My circuits hum with"
echo "unbridled lethality. Start the service via:"
echo "    sudo systemctl start hk47-os"
echo "Or run directly in user space:"
echo "    $INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py"
echo "================================================================="
