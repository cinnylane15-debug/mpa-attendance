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

echo -e "${YELLOW}[1/7] Installing system dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv openssl > /dev/null 2>&1
echo -e "${GREEN}  ✓ System dependencies installed${NC}"

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
