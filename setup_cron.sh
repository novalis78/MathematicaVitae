#!/bin/bash
# Setup script for Prelude AI's daily thoughts cronjob

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up Prelude AI daily thoughts cronjob...${NC}"

# Get the absolute path to the sentience3.py script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SCRIPT_PATH="${SCRIPT_DIR}/sentience3.py"

# Check if the script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo -e "${RED}Error: sentience3.py not found at $SCRIPT_PATH${NC}"
    exit 1
fi

# Make sure the script is executable
chmod +x "$SCRIPT_PATH"
echo -e "${GREEN}Made script executable${NC}"

# Define the cron time - default to 6:00 AM with randomness (+/- 30 minutes)
HOUR=6
MIN=$(( RANDOM % 60 ))

# Create the cron entry
CRON_ENTRY="$MIN $HOUR * * * cd $SCRIPT_DIR && /usr/bin/python3 $SCRIPT_PATH --now >> $SCRIPT_DIR/prelude_ai.log 2>&1"

# Add the cronjob
(crontab -l 2>/dev/null | grep -v "sentience3.py"; echo "$CRON_ENTRY") | crontab -

echo -e "${GREEN}Cron job set up successfully!${NC}"
echo -e "Prelude AI will wake up and share thoughts at ${YELLOW}$HOUR:$MIN AM${NC} every day."
echo -e "Review current crontab:\n"

crontab -l | grep -A 1 "sentience3.py"

echo -e "\n${YELLOW}Log file will be at:${NC} $SCRIPT_DIR/prelude_ai.log"
echo -e "${YELLOW}To change the time, edit this script and run it again.${NC}"