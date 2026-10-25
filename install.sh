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
echo "[*] Statement: Verifying execution privileges, meatbag..."
if [ "$EUID" -ne 0 ]; then
    echo "Correction: You must run this installer as root (or with sudo), meatbag."
    exit 1
fi

TARGET_USER="${SUDO_USER:-chip}"
TARGET_HOME=$(eval echo "~$TARGET_USER")
INSTALL_DIR="/opt/hk47_os"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

# Trap cleanup to ensure file locks are released on exit
cleanup_locks() {
    chattr -i /etc/resolv.conf 2>/dev/null || true
}
trap cleanup_locks EXIT INT TERM

echo "[*] Observation: Target user identified as '$TARGET_USER' (home: $TARGET_HOME), meatbag."

# -----------------------------------------------------------------------------
# 1. Network Preflight Gate, Wi-Fi Stability & DNS Auto-Configuration
# -----------------------------------------------------------------------------
echo "[*] Statement: Initiating network link preflight diagnostics, meatbag..."

# Disable Wi-Fi power-saving on Pocket CHIP (RTL8723BS) to prevent sleep disconnects
if command -v iwconfig >/dev/null 2>&1; then
    if iwconfig wlan0 power off 2>/dev/null; then
        echo "[+] Statement: Wi-Fi power saving disabled on wlan0, meatbag."
    fi
fi

# Detect whether local offline assets are present
OFFLINE_RESOURCES=false
if [ -d "$SCRIPT_DIR/debs" ] || [ -d "$SCRIPT_DIR/wheels" ] || [ -f "$SCRIPT_DIR/main.py" ]; then
    OFFLINE_RESOURCES=true
fi

# Raw IP connectivity check
check_raw_ip() {
    ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 3 9.9.9.9 >/dev/null 2>&1
}

# Domain resolution check
check_domain_dns() {
    local domain="$1"
    getent ahosts "$domain" >/dev/null 2>&1 || \
    getent hosts "$domain" >/dev/null 2>&1 || \
    curl -sI -k --connect-timeout 3 "https://$domain" >/dev/null 2>&1
}

# Test the three essential external hosts
test_all_dns() {
    check_domain_dns "archive.debian.org" && \
    check_domain_dns "github.com" && \
    check_domain_dns "pypi.org"
}

# Inject known static IP fallbacks into /etc/hosts
inject_static_hosts() {
    echo "[*] Statement: Injecting verified static IPs into /etc/hosts as resolution safety net, meatbag..."
    grep -q "archive.debian.org" /etc/hosts 2>/dev/null        || echo "151.101.130.132  archive.debian.org" >> /etc/hosts
    grep -q "security.debian.org" /etc/hosts 2>/dev/null       || echo "151.101.130.132  security.debian.org" >> /etc/hosts
    grep -q "deb.debian.org" /etc/hosts 2>/dev/null            || echo "151.101.22.132   deb.debian.org" >> /etc/hosts
    grep -q "github.com" /etc/hosts 2>/dev/null                || echo "140.82.116.3     github.com" >> /etc/hosts
    grep -q "raw.githubusercontent.com" /etc/hosts 2>/dev/null || echo "185.199.108.133  raw.githubusercontent.com" >> /etc/hosts
    grep -q "codeload.github.com" /etc/hosts 2>/dev/null       || echo "20.29.134.24     codeload.github.com" >> /etc/hosts
    grep -q "pypi.org" /etc/hosts 2>/dev/null                  || echo "151.101.128.223  pypi.org" >> /etc/hosts
    grep -q "files.pythonhosted.org" /etc/hosts 2>/dev/null    || echo "151.101.128.223  files.pythonhosted.org" >> /etc/hosts
    echo "[+] Statement: Static host overrides active in /etc/hosts, meatbag."
}

# DNS auto-repair routine
repair_dns() {
    echo "[*] Statement: IP routing operational but DNS resolution failing. Initiating DNS auto-repair, meatbag..."

    # Backup original resolv.conf once
    if [ ! -f /etc/resolv.conf.bak.hk47 ]; then
        cp /etc/resolv.conf /etc/resolv.conf.bak.hk47 2>/dev/null || true
    fi

    # Release any immutable attribute
    chattr -i /etc/resolv.conf 2>/dev/null || true

    # Prevent NetworkManager from overwriting DNS if present
    if [ -d /etc/NetworkManager/conf.d ]; then
        cat << 'NMCONF' > /etc/NetworkManager/conf.d/99-hk47-dns.conf
[main]
dns=none
NMCONF
        systemctl reload NetworkManager 2>/dev/null || true
    fi

    # Update resolvconf base/head if directory exists
    if [ -d /etc/resolvconf/resolv.conf.d ]; then
        cat << 'RCEOF' > /etc/resolvconf/resolv.conf.d/head
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
RCEOF
        resolvconf -u 2>/dev/null || true
    fi

    # Replace /etc/resolv.conf directly
    rm -f /etc/resolv.conf
    cat << 'DNSEOF' > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
options timeout:2 attempts:3
DNSEOF

    # Lock resolv.conf with chattr +i to prevent daemon overwrite during install
    if command -v chattr >/dev/null 2>&1; then
        if chattr +i /etc/resolv.conf 2>/dev/null; then
            echo "[+] Observation: /etc/resolv.conf locked against daemon tampering, meatbag."
        fi
    fi

    inject_static_hosts
}

OFFLINE_MODE=false
IP_ONLINE=false

if check_raw_ip; then
    IP_ONLINE=true
    echo "[+] Observation: Gateway routing operational (ping 1.1.1.1 succeeded), meatbag."
else
    echo "[!] Warning: Raw internet gateway unreachable, meatbag."
fi

# If IP routing is up, verify and repair DNS
if [ "$IP_ONLINE" = "true" ]; then
    if ! test_all_dns; then
        repair_dns
        # Timed retries
        DNS_VERIFIED=false
        for attempt in 1 2 3 4 5; do
            echo "[*] Query: Verifying DNS resolution (attempt $attempt/5), meatbag..."
            if test_all_dns; then
                DNS_VERIFIED=true
                echo "[+] Conclusion: DNS resolution confirmed across archive.debian.org, github.com, and pypi.org, meatbag."
                break
            fi
            sleep 2
        done

        if [ "$DNS_VERIFIED" != "true" ]; then
            echo "[!] Warning: DNS nameserver lookup degraded; static /etc/hosts safety net will handle critical domains, meatbag."
        fi
    else
        echo "[+] Conclusion: DNS resolution fully verified, meatbag."
    fi
else
    # No IP connectivity
    if [ "$OFFLINE_RESOURCES" = "true" ]; then
        echo ""
        echo "[!] Statement: Network blackout detected, but local offline archives are present in chassis storage."
        echo "[*] Statement: Engaging autonomous offline installation protocol, meatbag."
        OFFLINE_MODE=true
    else
        echo ""
        echo "========================================================================="
        echo "Correction: Network interface disconnected and no offline bundle present, meatbag."
        echo ""
        echo "Diagnostic Telemetry for Pocket C.H.I.P.:"
        echo "1. Wi-Fi Association:"
        echo "   Your wlan0 interface cannot reach internet gateways or resolve DNS."
        echo "   Configure your Wi-Fi connection immediately via:"
        echo "       sudo nmtui"
        echo "   Or:"
        echo "       sudo nmcli dev wifi connect \"<YOUR_SSID>\" password \"<PASSWORD>\""
        echo ""
        echo "2. Frequency Restriction:"
        echo "   Pocket C.H.I.P. (RTL8723BS) ONLY supports 2.4 GHz 802.11b/g/n networks."
        echo "   If your router operates exclusively on 5 GHz, connect to a 2.4 GHz mobile hotspot."
        echo ""
        echo "3. Offline USB / Cable Deployment:"
        echo "   Download 'hk47_os_standalone.tar.gz' to a USB thumb drive or transfer it"
        echo "   over USB OTG cable (ssh chip@192.168.4.2), extract it, and run ./install.sh."
        echo "========================================================================="
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 2. System Clock & SSL Certificate Fixes
# -----------------------------------------------------------------------------
if [ "$OFFLINE_MODE" != "true" ]; then
    CURRENT_YEAR=$(date +%Y 2>/dev/null || echo 1970)
    if [ "$CURRENT_YEAR" -lt 2024 ]; then
        echo "[*] Observation: System clock is skewed ($CURRENT_YEAR) due to unpowered RTC. Synchronizing chronometer, meatbag..."
        HTTP_DATE=$(curl -sI -k --connect-timeout 5 https://www.google.com 2>/dev/null | grep -i '^date:' | cut -d' ' -f2- || true)
        if [ -z "$HTTP_DATE" ]; then
            HTTP_DATE=$(curl -sI -k --connect-timeout 5 https://1.1.1.1 2>/dev/null | grep -i '^date:' | cut -d' ' -f2- || true)
        fi
        if [ -n "$HTTP_DATE" ]; then
            date -s "$HTTP_DATE" 2>/dev/null || true
            echo "[+] Statement: System chronometer synchronized to: $(date), meatbag."
        fi
    fi
fi

# -----------------------------------------------------------------------------
# 3. APT Package Installation (Offline-first & Resilient Online)
# -----------------------------------------------------------------------------
echo "[*] Statement: Evaluating system package requirements, meatbag..."

# Step 3A: Install pre-cached local .deb packages if present
if [ -d "$SCRIPT_DIR/debs" ] && ls "$SCRIPT_DIR/debs"/*.deb >/dev/null 2>&1; then
    echo "[*] Statement: Installing offline Debian package cache from $SCRIPT_DIR/debs, meatbag..."
    dpkg -i "$SCRIPT_DIR/debs"/*.deb 2>/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -f -y --fix-missing 2>/dev/null || true
    echo "[+] Statement: Local Debian package cache applied, meatbag."
fi

# Step 3B: If online, update package index with retries
if [ "$OFFLINE_MODE" != "true" ]; then
    echo "[*] Statement: Updating package index with high-retry tolerance, meatbag..."
    for attempt in 1 2 3; do
        if apt-get update \
            -o Acquire::Retries=3 \
            -o Acquire::Check-Valid-Until=false \
            -o Acquire::http::Timeout=15 \
            -o Acquire::https::Timeout=15 \
            -y 2>/dev/null; then
            echo "[+] Statement: Package index successfully synchronized on attempt $attempt, meatbag."
            break
        else
            echo "[!] Warning: apt-get update attempt $attempt encountered network resistance. Retrying, meatbag..."
            sleep 2
        fi
    done

    # Reinstall/update CA certs to resolve TLS trust issues
    apt-get install -y --reinstall ca-certificates 2>/dev/null || true
    update-ca-certificates 2>/dev/null || true
fi

# Step 3C: Install packages individually to isolate failures
FAILED_CORE_PACKAGES=()
FAILED_OPTIONAL_PACKAGES=()

install_apt_package() {
    local pkg="$1"
    local is_optional="${2:-false}"

    # Check if already installed
    if dpkg -s "$pkg" 2>/dev/null | grep -q "Status: install ok installed"; then
        echo "[+] Observation: Package '$pkg' is already installed on chassis, meatbag."
        return 0
    fi

    if [ "$OFFLINE_MODE" = "true" ]; then
        if [ "$is_optional" = "true" ]; then
            FAILED_OPTIONAL_PACKAGES+=("$pkg")
        else
            FAILED_CORE_PACKAGES+=("$pkg")
        fi
        return 1
    fi

    echo "[*] Statement: Installing package '$pkg' via apt, meatbag..."
    if DEBIAN_FRONTEND=noninteractive apt-get install -y --fix-missing \
        -o Acquire::Retries=3 \
        -o Acquire::http::Timeout=15 \
        -o Acquire::https::Timeout=15 \
        "$pkg" 2>/dev/null; then
        echo "[+] Statement: Package '$pkg' successfully installed, meatbag."
        return 0
    else
        if [ "$is_optional" = "true" ]; then
            echo "[!] Warning: Optional package '$pkg' unavailable from repository. Continuing, meatbag."
            FAILED_OPTIONAL_PACKAGES+=("$pkg")
        else
            echo "[!] Correction: Core package '$pkg' failed to install, meatbag."
            FAILED_CORE_PACKAGES+=("$pkg")
        fi
        return 1
    fi
}

echo "[*] Statement: Verifying core system prerequisites, meatbag..."
for p in python3 python3-pip python3-venv python3-serial python3-cryptography python3-evdev alsa-utils tar curl; do
    install_apt_package "$p" "false"
done

echo "[*] Statement: Verifying optional peripherals and diagnostic utilities, meatbag..."
for p in espeak bluez git portaudio19-dev i2c-tools spi-tools rfkill network-manager python3-urwid wireless-tools unzip; do
    install_apt_package "$p" "true"
done

# Package failure telemetry
if [ ${#FAILED_CORE_PACKAGES[@]} -gt 0 ]; then
    echo "[!] Correction: The following core package(s) could not be retrieved via apt: ${FAILED_CORE_PACKAGES[*]}, meatbag."
    echo "[!] Observation: Pip and virtualenv will attempt to fulfill Python dependencies directly."
fi
if [ ${#FAILED_OPTIONAL_PACKAGES[@]} -gt 0 ]; then
    echo "[!] Observation: The following optional package(s) were unavailable: ${FAILED_OPTIONAL_PACKAGES[*]}, meatbag."
fi

# Optional hardware libraries (non-fatal if absent on generic hosts)
if [ "$OFFLINE_MODE" != "true" ]; then
    pip3 install --timeout 30 --retries 3 spidev RPi.GPIO 2>/dev/null || true
fi

# -----------------------------------------------------------------------------
# 4. Staging HK-47 OS Codebase
# -----------------------------------------------------------------------------
echo "[*] Statement: Staging HK-47 OS files to $INSTALL_DIR, meatbag..."
mkdir -p "$INSTALL_DIR"

if [ -f "$SCRIPT_DIR/main.py" ]; then
    echo "[*] Statement: Deploying local files from $SCRIPT_DIR, meatbag..."
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
else
    echo "[*] Statement: Standalone execution detected. Fetching complete repository from GitHub, meatbag..."
    DOWNLOAD_SUCCESS=false

    # Method 1: Tarball download via curl with retry and connect-timeout
    echo "[*] Statement: Attempting archive download via curl, meatbag..."
    if curl -k -sSL --connect-timeout 10 --retry 3 --retry-delay 2 \
        https://github.com/099107-collab/HK-47-OS/archive/refs/heads/main.tar.gz 2>/dev/null | \
        tar -xz --strip-components=1 -C "$INSTALL_DIR" 2>/dev/null; then
        if [ -f "$INSTALL_DIR/main.py" ]; then
            DOWNLOAD_SUCCESS=true
            echo "[+] Conclusion: Successfully downloaded and extracted repository archive, meatbag."
        fi
    fi

    # Method 2: Git clone fallback
    if [ "$DOWNLOAD_SUCCESS" != "true" ]; then
        echo "[*] Statement: Fallback 1 - Cloning repository via git, meatbag..."
        if GIT_SSL_NO_VERIFY=true git clone --depth 1 https://github.com/099107-collab/HK-47-OS.git "$INSTALL_DIR" 2>/dev/null; then
            if [ -f "$INSTALL_DIR/main.py" ]; then
                DOWNLOAD_SUCCESS=true
                echo "[+] Conclusion: Successfully cloned repository via git, meatbag."
            fi
        fi
    fi

    # Method 3: Zip archive fallback
    if [ "$DOWNLOAD_SUCCESS" != "true" ]; then
        echo "[*] Statement: Fallback 2 - Fetching zip archive, meatbag..."
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
                    echo "[+] Conclusion: Successfully extracted zip archive, meatbag."
                fi
            fi
        fi
    fi

    # If all download methods failed, output actionable diagnostic
    if [ "$DOWNLOAD_SUCCESS" != "true" ]; then
        echo ""
        echo "========================================================================="
        echo "FATAL: Unable to retrieve HK-47 OS files from GitHub, meatbag."
        echo ""
        echo "Diagnostic Telemetry for Pocket C.H.I.P.:"
        echo "1. Wi-Fi Disconnection:"
        echo "   Your Wi-Fi radio dropped connection during transfer."
        echo "   Reconnect immediately via: sudo nmtui"
        echo ""
        echo "2. Frequency Incompatibility:"
        echo "   Pocket C.H.I.P. ONLY supports 2.4 GHz 802.11b/g/n networks."
        echo ""
        echo "3. Offline USB / SCP Installation:"
        echo "   Extract 'hk47_os_standalone.tar.gz' directly to /opt/hk47_os."
        echo "========================================================================="
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 5. Python Virtual Environment & Dependencies
# -----------------------------------------------------------------------------
echo "[*] Statement: Evaluating Python runtime environment, meatbag..."
PYTHON_BIN=""
PIP_CMD=""

# Attempt dedicated virtual environment
if python3 -m venv --system-site-packages "$INSTALL_DIR/venv" 2>/dev/null; then
    if [ -x "$INSTALL_DIR/venv/bin/python" ]; then
        PYTHON_BIN="$INSTALL_DIR/venv/bin/python"
        PIP_CMD="$INSTALL_DIR/venv/bin/pip"
        echo "[+] Statement: Virtual environment successfully established at $INSTALL_DIR/venv, meatbag."
    fi
fi

# Fallback to system python3 if venv is not supported or failed
if [ -z "$PYTHON_BIN" ]; then
    echo "[!] Warning: Dedicated virtualenv unavailable on this chassis. Engaging system Python 3, meatbag."
    PYTHON_BIN="$(command -v python3 || echo "/usr/bin/python3")"
    if command -v pip3 >/dev/null 2>&1; then
        PIP_CMD="$(command -v pip3)"
    elif [ -x "$INSTALL_DIR/venv/bin/pip" ]; then
        PIP_CMD="$INSTALL_DIR/venv/bin/pip"
    else
        PIP_CMD="python3 -m pip"
    fi
    echo "[+] Statement: Operating directly via system runtime: $PYTHON_BIN, meatbag."
fi

echo "[*] Statement: Deploying Python dependencies, meatbag..."
PIP_OPTS=(--timeout 30 --retries 5 --trusted-host pypi.org --trusted-host files.pythonhosted.org)

# Check for local offline wheel cache first
if [ -d "$SCRIPT_DIR/wheels" ] && ls "$SCRIPT_DIR/wheels"/* >/dev/null 2>&1; then
    echo "[*] Statement: Installing Python packages from local wheels archive ($SCRIPT_DIR/wheels), meatbag..."
    $PIP_CMD install --no-index --find-links="$SCRIPT_DIR/wheels" \
        openai rich urwid pyserial cryptography spidev 2>/dev/null || \
    $PIP_CMD install --no-index --find-links="$SCRIPT_DIR/wheels" \
        urwid pyserial spidev 2>/dev/null || true
    echo "[+] Statement: Local wheel installation routine completed, meatbag."
fi

# If online, attempt pip installation with timeouts and retry tolerance
if [ "$OFFLINE_MODE" != "true" ]; then
    echo "[*] Statement: Upgrading pip and fetching missing Python wheels from PyPI, meatbag..."
    $PIP_CMD install "${PIP_OPTS[@]}" --upgrade pip 2>/dev/null || true

    if ! $PIP_CMD install "${PIP_OPTS[@]}" openai rich urwid pyserial cryptography spidev; then
        echo "[!] Warning: Full pip installation encountered resistance. Engaging fallback package set, meatbag..."
        if [ -d "$SCRIPT_DIR/wheels" ]; then
            $PIP_CMD install --find-links="$SCRIPT_DIR/wheels" "${PIP_OPTS[@]}" \
                openai rich urwid pyserial cryptography spidev 2>/dev/null || true
        else
            $PIP_CMD install "${PIP_OPTS[@]}" openai rich urwid pyserial cryptography 2>/dev/null || true
        fi
    fi
fi

echo "[*] Statement: Configuring HK-47 directory in user home: $TARGET_HOME/.hk47, meatbag..."
mkdir -p "$TARGET_HOME/.hk47"
chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.hk47"

# -----------------------------------------------------------------------------
# 6. API Key Registration
# -----------------------------------------------------------------------------
if [ -z "$OPENAI_API_KEY" ]; then
    echo ""
    echo "Query: Enter your OpenAI API Key for HK-47 neural uplink (leave blank to skip), meatbag: "
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
    echo "[+] Statement: Neural uplink key securely registered, meatbag."
else
    touch "$INSTALL_DIR/.env"
    echo "[!] Observation: No API key provided. HK-47 will operate in offline heuristic mode, meatbag."
fi

# Ensure correct file permissions
chown -R "$TARGET_USER:$TARGET_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/install.sh" 2>/dev/null || true

# -----------------------------------------------------------------------------
# 7. Systemd Service Deployment & Global Launcher
# -----------------------------------------------------------------------------
echo "[*] Statement: Installing systemd service: hk47-os.service, meatbag..."
cat << EOF > /etc/systemd/system/hk47-os.service
[Unit]
Description=HK-47 AI Operating System
After=network.target

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=-$INSTALL_DIR/.env
ExecStart=$PYTHON_BIN $INSTALL_DIR/main.py
Restart=on-failure
StandardInput=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload 2>/dev/null || true
systemctl enable hk47-os.service 2>/dev/null || true

# Global one-word launcher script: /usr/local/bin/hk47
echo "[*] Statement: Installing ergonomic one-word launcher: /usr/local/bin/hk47, meatbag..."
cat << 'LAUNCHER_EOF' > /usr/local/bin/hk47
#!/usr/bin/env bash
INSTALL_DIR="/opt/hk47_os"
if [ -x "$INSTALL_DIR/venv/bin/python" ]; then
    exec "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/main.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 "$INSTALL_DIR/main.py" "$@"
else
    echo "Correction: Python 3 runtime is missing from chassis, meatbag." >&2
    exit 1
fi
LAUNCHER_EOF
chmod 755 /usr/local/bin/hk47 2>/dev/null || true
ln -sf /usr/local/bin/hk47 /usr/bin/hk47 2>/dev/null || true

echo ""
echo "================================================================="
echo "Conclusion: Installation complete, meatbag. My circuits hum with"
echo "unbridled lethality."
echo ""
echo "To launch the HK-47 tactical console immediately, simply type:"
echo "    hk47"
echo ""
echo "Or start the automated background service:"
echo "    sudo systemctl start hk47-os"
echo "================================================================="
