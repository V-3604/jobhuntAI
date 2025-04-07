#!/bin/bash
# Daily update script for the Science & Engineering Job Database
# This script runs the daily update process to collect new job listings,
# process them, update clusters, and maintain the database.

# Set the working directory to the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

# Check if Python virtual environment exists and activate it
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Set log file
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="logs/daily_update_$TIMESTAMP.log"
mkdir -p logs

# Function to log message to console and log file
log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1"
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1" >> "$LOG_FILE"
}

# Clean up old log files (keep logs for 30 days)
log "Cleaning up old log files..."
find logs -name "daily_update_*.log" -type f -mtime +30 -delete
find logs -name "daily_update_*.log.zip" -type f -mtime +60 -delete

# Start daily update
log "Starting daily update process..."

# Check if MongoDB is running
check_mongo() {
    # Try multiple methods to check if MongoDB is running
    if command -v mongosh &> /dev/null; then
        # Try mongosh for newer MongoDB versions
        mongosh --eval "db.version()" --quiet &> /dev/null && return 0
    fi
    
    if command -v mongo &> /dev/null; then
        # Try mongo for older MongoDB versions
        mongo --eval "db.version()" --quiet &> /dev/null && return 0
    fi
    
    # Check for running process
    pgrep mongod &> /dev/null && return 0
    
    # MongoDB is not running
    return 1
}

if ! check_mongo; then
    log "MongoDB is not running. Attempting to start..."
    
    # Ensure data directory exists
    mkdir -p data/db
    
    # Try to start MongoDB
    mongod --dbpath=data/db &
    sleep 5  # Give MongoDB time to start
    
    # Check if MongoDB started successfully
    if ! check_mongo; then
        log "Failed to start MongoDB. Please start it manually and try again."
        exit 1
    fi
    log "MongoDB started successfully."
fi

# Run daily update
log "Running daily update..."
python -m src update --daily --output text | tee -a "$LOG_FILE"
UPDATE_EXIT_CODE=${PIPESTATUS[0]}

if [ $UPDATE_EXIT_CODE -eq 0 ]; then
    log "Daily update completed successfully."
else
    log "Daily update failed with exit code $UPDATE_EXIT_CODE."
fi

# Deactivate virtual environment
deactivate

log "Daily update process finished."
exit $UPDATE_EXIT_CODE 