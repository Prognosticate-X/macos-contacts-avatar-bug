#!/usr/bin/env bash
# ==============================================================================
# macOS Contacts & Messages Avatar Sync Bug Diagnostic Logger
# Tool to capture Unified Logging events for likeness and poster sync regression.
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
OUTPUT_DIR="${1:-./logs}"
mkdir -p "$OUTPUT_DIR"
RAW_LOG="$OUTPUT_DIR/capture_${TIMESTAMP}.log"
SANITIZED_LOG="$OUTPUT_DIR/capture_${TIMESTAMP}_sanitized.log"

echo -e "${CYAN}${BOLD}====================================================================${NC}"
echo -e "${CYAN}${BOLD}   macOS 27 Contacts Avatar Regression Diagnostic Capture Tool      ${NC}"
echo -e "${CYAN}${BOLD}====================================================================${NC}"
echo -e "${YELLOW}This tool monitors Unified Logging for Contacts, Messages, postersyncd,${NC}"
echo -e "${YELLOW}contactsd, and AddressBookSourceSync to capture the avatar reversion bug.${NC}\n"

echo -e "${BOLD}Target Output File:${NC} $RAW_LOG"
echo -e "${BOLD}Instructions:${NC}"
echo -e " 1. Keep this terminal window open."
echo -e " 2. Open ${GREEN}Contacts.app${NC}."
echo -e " 3. Select any contact, click ${YELLOW}'Edit'${NC}, change avatar (photo/Memoji/Emoji), click ${GREEN}'Done'${NC}."
echo -e " 4. Wait for ~20 seconds until you see the avatar revert to a monogram initial."
echo -e " 5. Press ${RED}Ctrl+C${NC} in this window to stop capture.\n"

echo -e "${GREEN}Starting log stream now... (Press Ctrl+C when finished)${NC}\n"

FILTER='process == "Contacts" OR process == "Messages" OR process == "contactsd" OR process == "postersyncd" OR process == "AddressBookSourceSync"'

# Trap SIGINT to safely terminate and sanitize
cleanup() {
    echo -e "\n\n${YELLOW}[*] Log streaming stopped.${NC}"
    if [ -f "$RAW_LOG" ] && [ -s "$RAW_LOG" ]; then
        echo -e "${GREEN}[✔] Raw log saved:${NC} $RAW_LOG ($(du -h "$RAW_LOG" | cut -f1))"
        
        # Sanitize local username
        CURRENT_USER=$(whoami)
        sed "s/${CURRENT_USER}/<username>/g" "$RAW_LOG" > "$SANITIZED_LOG"
        echo -e "${GREEN}[✔] Sanitized log generated:${NC} $SANITIZED_LOG"
        
        echo -e "\n${CYAN}Running automated diagnosis on the captured log...${NC}"
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [ -f "$SCRIPT_DIR/analyze_log.py" ]; then
            python3 "$SCRIPT_DIR/analyze_log.py" "$SANITIZED_LOG" || true
        fi
    else
        echo -e "${RED}[!] No log data captured.${NC}"
    fi
    exit 0
}

trap cleanup INT TERM

# Start stream
log stream --level debug --predicate "$FILTER" > "$RAW_LOG"
