#!/usr/bin/env bash
# MPA Server Management API — Bootstrap Script
# Usage: sudo bash bootstrap.sh
# Designed for Ubuntu 22.04 / 24.04

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  MPA Server Management API - Bootstrap       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (sudo bash bootstrap.sh)${NC}"
    exit 1
fi

MGMT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$MGMT_DIR"

# --- DNS / Network Pre-check ---
echo -e "${YELLOW}[0/7] Checking network connectivity...${NC}"
if ! getent hosts archive.ubuntu.com > /dev/null 2>&1; then
    echo -e "${RED}  ✗ DNS resolution failed — cannot resolve archive.ubuntu.com${NC}"
    echo ""
    echo -e "  Your server cannot resolve domain names. Checking DNS config..."
    echo ""

    # Show current DNS config
    echo -e "  Current /etc/resolv.conf:"
    cat /etc/resolv.conf 2>/dev/null | grep -v "^#" | head -5 | sed 's/^/    /'
    echo ""

    # Try to auto-fix by adding Google DNS
    echo -e "${YELLOW}  Attempting to fix DNS by adding Google nameservers...${NC}"

    # Check if systemd-resolved is managing DNS
    if systemctl is-active systemd-resolved > /dev/null 2>&1; then
        # Add DNS to resolved config
        mkdir -p /etc/systemd/resolved.conf.d
        cat > /etc/systemd/resolved.conf.d/dns.conf <<DNSEOF
[Resolve]
DNS=8.8.8.8 8.8.4.4 1.1.1.1
FallbackDNS=208.67.222.222
DNSEOF
        systemctl restart systemd-resolved
        sleep 2
    else
        # Direct resolv.conf edit
        if [ ! -L /etc/resolv.conf ]; then
            cp /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null || true
            cat > /etc/resolv.conf <<DNSEOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
DNSEOF
        else
            # resolv.conf is a symlink (likely managed by systemd/netplan)
            echo "nameserver 8.8.8.8" >> /etc/resolv.conf 2>/dev/null || true
        fi
    fi

    # Re-check DNS
    if getent hosts archive.ubuntu.com > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ DNS fixed! Continuing...${NC}"
    else
        echo -e "${RED}  ✗ DNS still not working. Please fix manually:${NC}"
        echo ""
        echo -e "  Option 1: Edit /etc/resolv.conf and add:"
        echo -e "    nameserver 8.8.8.8"
        echo -e "    nameserver 8.8.4.4"
        echo ""
        echo -e "  Option 2: If using Netplan, edit /etc/netplan/*.yaml and add:"
        echo -e "    nameservers:"
        echo -e "      addresses: [8.8.8.8, 8.8.4.4]"
        echo -e "    Then run: sudo netplan apply"
        echo ""
        echo -e "  Option 3: Check your network cable / DHCP server"
        echo ""

        # Check if deps are already installed — can continue offline
        if command -v python3 &>/dev/null && command -v openssl &>/dev/null && python3 -c "import venv" 2>/dev/null; then
            echo -e "${YELLOW}  python3, venv, and openssl are already installed.${NC}"
            echo -e "${YELLOW}  Continuing without apt (offline mode)...${NC}"
            SKIP_APT=1
        else
            echo -e "${RED}  Cannot continue — python3/openssl not installed and apt unavailable.${NC}"
            echo -e "${RED}  Fix DNS first, then re-run this script.${NC}"
            exit 1
        fi
    fi
else
    echo -e "${GREEN}  ✓ DNS resolution working${NC}"
fi

echo -e "${YELLOW}[1/7] Installing system dependencies...${NC}"
if [ "${SKIP_APT:-0}" = "1" ]; then
    echo -e "${GREEN}  ✓ Dependencies already installed (offline mode)${NC}"
elif command -v python3 &>/dev/null && command -v openssl &>/dev/null && python3 -c "import venv" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Dependencies already installed, skipping apt${NC}"
else
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv openssl > /dev/null 2>&1
    echo -e "${GREEN}  ✓ System dependencies installed${NC}"
fi

echo -e "${YELLOW}[2/7] Creating Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}  ✓ Python venv created and packages installed${NC}"

echo -e "${YELLOW}[3/7] Generating SSL certificate...${NC}"
if [ ! -f cert.pem ] || [ ! -f key.pem ]; then
    openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
        -days 365 -nodes -subj "/CN=$(hostname)" 2>/dev/null
    echo -e "${GREEN}  ✓ SSL certificate generated (self-signed, valid 365 days)${NC}"
else
    echo -e "${GREEN}  ✓ SSL certificate already exists, skipping${NC}"
fi

echo -e "${YELLOW}[4/7] Generating secrets and creating .env...${NC}"
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '=/+' | head -c 20)
JWT_SECRET=$(openssl rand -hex 32)
API_PORT=8443

if [ ! -f .env ]; then
    cat > .env <<EOL
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASS}
JWT_SECRET=${JWT_SECRET}
API_PORT=${API_PORT}
SSL_CERT=${MGMT_DIR}/cert.pem
SSL_KEY=${MGMT_DIR}/key.pem
DB_PATH=${MGMT_DIR}/mgmt.db
STACKS_DIR=${MGMT_DIR}/stacks
ALLOWED_IPS=
RATE_LIMIT=100
EOL
    echo -e "${GREEN}  ✓ Configuration file created${NC}"
else
    echo -e "${GREEN}  ✓ .env already exists, skipping (delete to regenerate)${NC}"
    # Read existing password for display
    ADMIN_PASS=$(grep ADMIN_PASSWORD .env | cut -d= -f2)
fi

echo -e "${YELLOW}[5/7] Initializing database...${NC}"
source venv/bin/activate
cd "$MGMT_DIR"
python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from database import init_db
asyncio.run(init_db())
print('  Database initialized')
"
echo -e "${GREEN}  ✓ Database ready${NC}"

echo -e "${YELLOW}[6/7] Creating stacks directory...${NC}"
mkdir -p stacks
echo -e "${GREEN}  ✓ Stacks directory created${NC}"

echo -e "${YELLOW}[7/7] Installing systemd service...${NC}"
sed "s|MGMT_DIR_PLACEHOLDER|${MGMT_DIR}|g" server-mgmt.service > /etc/systemd/system/mpa-server-mgmt.service
systemctl daemon-reload
systemctl enable mpa-server-mgmt.service
systemctl restart mpa-server-mgmt.service
echo -e "${GREEN}  ✓ systemd service installed and started${NC}"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup Complete!                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  API URL:      ${YELLOW}https://$(hostname -I | awk '{print $1}'):${API_PORT}${NC}"
echo -e "  Health Check: ${YELLOW}https://$(hostname -I | awk '{print $1}'):${API_PORT}/health${NC}"
echo -e "  API Docs:     ${YELLOW}https://$(hostname -I | awk '{print $1}'):${API_PORT}/docs${NC}"
echo ""
echo -e "  ${RED}╔════════════════════════════════════════════╗${NC}"
echo -e "  ${RED}║  SAVE THESE CREDENTIALS — SHOWN ONCE ONLY  ║${NC}"
echo -e "  ${RED}╠════════════════════════════════════════════╣${NC}"
echo -e "  ${RED}║  Username: admin                            ║${NC}"
echo -e "  ${RED}║  Password: ${ADMIN_PASS}$(printf '%*s' $((22 - ${#ADMIN_PASS})) '')║${NC}"
echo -e "  ${RED}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  To check status: ${YELLOW}systemctl status mpa-server-mgmt${NC}"
echo -e "  To view logs:    ${YELLOW}journalctl -u mpa-server-mgmt -f${NC}"
echo ""
