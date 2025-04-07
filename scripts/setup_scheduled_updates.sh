#!/bin/bash
# Setup scheduled updates for the Science & Engineering Job Database
# This script sets up a cron job to run the daily update script automatically

# Set the working directory to the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# Get the absolute path to the daily update script
DAILY_UPDATE_SCRIPT="$SCRIPT_DIR/daily_update.sh"

# Check if the daily update script exists
if [ ! -f "$DAILY_UPDATE_SCRIPT" ]; then
    echo "Error: Daily update script not found at $DAILY_UPDATE_SCRIPT"
    exit 1
fi

# Make sure the daily update script is executable
chmod +x "$DAILY_UPDATE_SCRIPT"

# Determine the current user
CURRENT_USER=$(whoami)

# Default schedule: Run every day at 2:00 AM
DEFAULT_SCHEDULE="0 2 * * *"
SCHEDULE=${1:-$DEFAULT_SCHEDULE}

echo "Setting up scheduled updates for the Science & Engineering Job Database."
echo "Schedule: $SCHEDULE (cron format)"
echo "Script: $DAILY_UPDATE_SCRIPT"
echo ""

# Create cron job entry with full path
CRON_ENTRY="$SCHEDULE cd $PROJECT_ROOT && $DAILY_UPDATE_SCRIPT > /dev/null 2>&1"

# Check if crontab exists and is accessible
if ! crontab -l &>/dev/null && [ "$?" -ne 0 ]; then
    echo "Error: Cannot access crontab. Please check permissions."
    exit 1
fi

# Add the cron job, removing any previous entries for the same script
(crontab -l 2>/dev/null | grep -v "$DAILY_UPDATE_SCRIPT" ; echo "$CRON_ENTRY") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Scheduled update successfully set up."
    echo "The system will automatically update the job database according to the schedule."
    echo ""
    echo "To check the current schedule, run: crontab -l"
    echo "To modify the schedule, run this script again with a different schedule."
    echo "Example: $0 \"0 4 * * *\"  (run every day at 4:00 AM)"
    echo "To remove the scheduled job, run: crontab -l | grep -v \"$DAILY_UPDATE_SCRIPT\" | crontab -"
else
    echo "❌ Error: Failed to set up scheduled update."
    echo "Please check permissions and try again."
    exit 1
fi

echo ""
echo "Current scheduled tasks:"
crontab -l | grep -v "^#"

exit 0 