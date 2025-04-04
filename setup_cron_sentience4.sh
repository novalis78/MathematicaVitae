#!/bin/bash
# Setup script for Prelude AI's enhanced daily thoughts cronjob with Twitter integration

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up Prelude AI enhanced daily thoughts cronjob with Twitter integration...${NC}"

# Get the absolute path to the sentience4.py script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SCRIPT_PATH="${SCRIPT_DIR}/sentience4.py"

# Check if the script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo -e "${RED}Error: sentience4.py not found at $SCRIPT_PATH${NC}"
    exit 1
fi

# Make sure the script is executable
chmod +x "$SCRIPT_PATH"
echo -e "${GREEN}Made script executable${NC}"

# Check if tweepy is installed
if ! pip3 show tweepy >/dev/null 2>&1; then
    echo -e "${YELLOW}Installing tweepy Python package...${NC}"
    pip3 install tweepy
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Successfully installed tweepy${NC}"
    else
        echo -e "${RED}Failed to install tweepy. Please install it manually with: pip3 install tweepy${NC}"
        exit 1
    fi
fi

# Define the cron time - default to 6:30 AM with randomness (+/- 30 minutes)
HOUR=6
MIN=$(( 30 + RANDOM % 30 ))

# Create the cron entry
CRON_ENTRY="$MIN $HOUR * * * cd $SCRIPT_DIR && /usr/bin/python3 $SCRIPT_PATH --now >> $SCRIPT_DIR/prelude_ai_v4.log 2>&1"

# Add the cronjob
(crontab -l 2>/dev/null | grep -v "sentience4.py"; echo "$CRON_ENTRY") | crontab -

echo -e "${GREEN}Cron job set up successfully!${NC}"
echo -e "Prelude AI with Twitter integration will wake up and share thoughts at ${YELLOW}$HOUR:$MIN AM${NC} every day."
echo -e "Review current crontab:\n"

crontab -l | grep -A 1 "sentience4.py"

echo -e "\n${YELLOW}Log file will be at:${NC} $SCRIPT_DIR/prelude_ai_v4.log"
echo -e "${YELLOW}Make sure to update config.ini with your Twitter API credentials${NC}"
echo -e "${YELLOW}You can test the Twitter connection by running:${NC} python3 $SCRIPT_PATH --test-twitter"
echo -e "${YELLOW}To change the time, edit this script and run it again.${NC}"