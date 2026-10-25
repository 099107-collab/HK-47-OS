#!/usr/bin/env bash
# =============================================================================
# HK-47 OS :: Automated Provisioning & Installation Script
# Target: Pocket CHIP (Allwinner R8, ARMhf, Debian Buster/Jessie) / Any Linux Host
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
# 1. Network Diagnostics, Wi-Fi Stability & DNS Auto-Configuration
# -----------------------------------------------------------------------------
echo "[*] Initializing network link verification..."

# Disable Wi-Fi power-saving on Pocket CHIP (RTL8723BS) to prevent sleep disconnects
if command -v iwconfig >/dev/null 2>&1; then
    iwconfig wlan0 power off 2>/dev/null && echo "[+] Wi-Fi power saving disabled on wlan0." || true
fi

# Verify DNS resolution to github.com
echo "[*] Testing DNS resolution for github.com..."
DNS_RESOLVED=false
if getent hosts github.com >/dev/null 2>&1 || curl -sI -k --connect-timeout 4 https://github.com >/dev/null 2>&1; then
    DNS_RESOLVED=true
    echo "[+] DNS resolution operational: github.com resolved."
else
    echo "[!] Warning: Cannot resolve github.com. Diagnosing link status..."
    
    # Check if raw IP routing to internet works
    IP_REACHABLE=false
    if ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
        IP_REACHABLE=true
    fi

    if [ "$IP_REACHABLE" = "true" ]; then
        echo "[+] Internet routing is active, but DNS nameservers are failing."
        echo "[*] Auto-injecting high-reliability public nameservers (1.1.1.1, 8.8.8.8, 9.9.9.9)..."
        cp /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null || true
        cat << 'DNSEOF' > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
DNSEOF
        # Retest DNS after nameserver update
        if getent hosts github.com >/dev/null 2>&1 || curl -sI -k --connect-timeout 4 https://github.com >/dev/null 2>&1; then
            DNS_RESOLVED=true
            echo "[+] DNS repair successful. github.com resolved."
        fi
    else
        echo "[!] CRITICAL WARNING: Network interface is disconnected or unreachable."
        echo "[!] Cannot reach internet gateways (1.1.1.1 / 8.8.8.8)."
        echo "[!] On Pocket C.H.I.P., ensure Wi-Fi is associated. Reconnect via:"
        echo "        sudo nmtui"
        echo "    Or: sudo nmcli dev wifi connect <SSID> password <PASS>"
    fi

    # Fallback: If DNS still failing but IP is routable, inject known GitHub IPs into /etc/hosts
    if [ "$DNS_RESOLVED" != "true" ] && [ "$IP_REACHABLE" = "true" ]; then
        echo "[*] Adding direct IP resolution fallback for GitHub to /etc/hosts..."
        grep -q "github.com" /etc/hosts 2>/dev/null || echo "140.82.121.4 github.com" >> /etc/hosts
        grep -q "raw.githubusercontent.com" /etc/hosts 2>/dev/null || echo "185.199.108.133 raw.githubusercontent.com" >> /etc/hosts
        grep -q "codeload.github.com" /etc/hosts 2>/dev/null || echo "140.82.121.9 codeload.github.com" >> /etc/hosts
        DNS_RESOLVED=true
    fi
fi

# -----------------------------------------------------------------------------
# 2. System Clock & SSL Certificate Fixes
# -----------------------------------------------------------------------------
CURRENT_YEAR=$(date +%Y 2>/dev/null || echo 1970)
if [ "$CURRENT_YEAR" -lt 2024 ]; then
    echo "[*] System clock is skewed ($CURRENT_YEAR) due to missing RTC battery. Synchronizing..."
    HTTP_DATE=$(curl -sI -k --connect-timeout 5 https://www.google.com 2>/dev/null | grep -i '^date:' | cut -d' ' -f2- || true)
    if [ -z "$HTTP_DATE" ]; then
        HTTP_DATE=$(curl -sI -k --connect-timeout 5 https://1.1.1.1 2>/dev/null | grep -i '^date:' | cut -d' ' -f2- || true)
    fi
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
    python3-urwid \
    python3-serial \
    git \
    portaudio19-dev \
    i2c-tools \
    spi-tools \
    rfkill \
    network-manager \
    wireless-tools \
    alsa-utils \
    tar \
    unzip \
    curl || true

# Optional hardware libraries (non-fatal if absent on generic hosts)
pip3 install spidev RPi.GPIO 2>/dev/null || true

# -----------------------------------------------------------------------------
# 3. Staging HK-47 OS Codebase
# -----------------------------------------------------------------------------
echo "[*] Staging HK-47 OS files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

if [ -f "$SCRIPT_DIR/main.py" ]; then
    echo "[*] Copying local files from $SCRIPT_DIR..."
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
else
    echo "[*] Standalone execution detected. Fetching complete repository from GitHub..."
    DOWNLOAD_SUCCESS=false

    # Method 1: Tarball download via curl with retry and connect-timeout
    echo "[*] Attempting archive download via curl..."
    if curl -k -sSL --connect-timeout 10 --retry 3 --retry-delay 2 \
        https://github.com/099107-collab/HK-47-OS/archive/refs/heads/main.tar.gz 2>/dev/null | \
        tar -xz --strip-components=1 -C "$INSTALL_DIR" 2>/dev/null; then
        if [ -f "$INSTALL_DIR/main.py" ]; then
            DOWNLOAD_SUCCESS=true
            echo "[+] Successfully downloaded and extracted repository archive."
        fi
    fi

    # Method 2: Git clone fallback
    if [ "$DOWNLOAD_SUCCESS" != "true" ]; then
        echo "[*] Fallback 1: Cloning repository via git..."
        if GIT_SSL_NO_VERIFY=true git clone --depth 1 https://github.com/099107-collab/HK-47-OS.git "$INSTALL_DIR" 2>/dev/null; then
            if [ -f "$INSTALL_DIR/main.py" ]; then
                DOWNLOAD_SUCCESS=true
                echo "[+] Successfully cloned repository via git."
            fi
        fi
    fi

    # Method 3: Zip archive fallback
    if [ "$DOWNLOAD_SUCCESS" != "true" ]; then
        echo "[*] Fallback 2: Fetching zip archive..."
        TMP_ZIP="/tmp/hk47_repo.zip"
        if curl -k -sSL --connect-timeout 10 --retry 2 \
            https://github.com/099107-collab/HK-47-OS/archive/refs/heads/main.zip -o "$TMP_ZIP" 2>/dev/null; then
            if command -v unzip >/dev/null 2>&1; then
                mkdir -p /tmp/hk47_extract
                unzip -q -o "$TMP_ZIP" -d /tmp/hk47_extract 2>/dev/null || true
                cp -r /tmp/hk47_extract/HK-47-OS-main/* "$INSTALL_DIR/" 2>/dev/null || true
                rm -rf /tmp/hk47_extract "$TMP_ZIP"
                if [ -f "$INSTALL_DIR/main.py" ]; then
                    DOWNLOAD_SUCCESS=true
                    echo "[+] Successfully extracted zip archive."
                fi
            fi
        fi
    fi

    # If all download methods failed, output actionable diagnostic
    if [ "$DOWNLOAD_SUCCESS" != "true" ]; then
        echo ""
        echo "========================================================================="
        echo "FATAL: Unable to retrieve HK-47 OS files from GitHub."
        echo ""
        echo "Diagnostic Analysis for Pocket C.H.I.P.:"
        echo "1. Wi-Fi Disconnection:"
        echo "   Your Wi-Fi radio is likely disconnected or dropped."
        echo "   Connect Wi-Fi now by running:"
        echo "       sudo nmtui"
        echo "   Or:"
        echo "       sudo nmcli dev wifi connect \"<YOUR_SSID>\" password \"<PASSWORD>\""
        echo ""
        echo "2. Wi-Fi Frequency Compatibility:"
        echo "   Pocket C.H.I.P. ONLY supports 2.4 GHz 802.11b/g/n networks."
        echo "   If your router uses 5 GHz only, connect to a 2.4 GHz phone mobile hotspot."
        echo ""
        echo "3. Offline USB / SCP Installation:"
        echo "   You can copy the standalone archive 'hk47_os_standalone.tar.gz' to a USB"
        echo "   drive or via SCP over USB OTG cable (chip@192.168.4.2) and extract it to"
        echo "   /opt/hk47_os to complete installation completely offline."
        echo "========================================================================="
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 4. Python Virtual Environment & Dependencies
# -----------------------------------------------------------------------------
echo "[*] Creating dedicated Python virtual environment (with system site-packages)..."
# Use --system-site-packages so Pocket CHIP can use apt pre-compiled cryptography/urwid
python3 -m venv --system-site-packages "$INSTALL_DIR/venv"

echo "[*] Installing Python dependencies into venv..."
"$INSTALL_DIR/venv/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org --upgrade pip 2>/dev/null || true
"$INSTALL_DIR/venv/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    openai rich urwid pyserial cryptography spidev 2>/dev/null || \
    "$INSTALL_DIR/venv/bin/pip" install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    openai rich urwid pyserial cryptography || true

echo "[*] Setting up HK-47 directory in user home: $TARGET_HOME/.hk47..."
mkdir -p "$TARGET_HOME/.hk47"
chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.hk47"

# -----------------------------------------------------------------------------
# 5. API Key Registration
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
chmod +x "$INSTALL_DIR/install.sh" 2>/dev/null || true

# -----------------------------------------------------------------------------
# 6. Systemd Service Deployment
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
