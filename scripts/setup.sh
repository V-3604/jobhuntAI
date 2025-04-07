#!/bin/bash
# Setup script for the Science & Engineering Job Database

echo "Setting up Science & Engineering Job Database..."

# Create necessary directories
echo "Creating required directories..."
mkdir -p logs
mkdir -p data/db
mkdir -p config

# Check if config.yaml exists, if not, copy from template
if [ ! -f "config/config.yaml" ] && [ -f "config/config.yaml.template" ]; then
    echo "Copying config template..."
    cp config/config.yaml.template config/config.yaml
    echo "Please edit config/config.yaml with your settings."
fi

# Create and activate Python virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ] && [ -f ".env.sample" ]; then
    echo "Creating .env file from template..."
    cp .env.sample .env
    echo "Please edit .env file with your API keys and configuration settings."
fi

# Check for MongoDB
echo "Checking for MongoDB installation..."
if command -v mongod &> /dev/null; then
    echo "MongoDB found. Setting up data directory..."
    mkdir -p data/db
    echo "To start MongoDB, run: mongod --dbpath=data/db"
elif command -v brew &> /dev/null; then
    echo "MongoDB not found but Homebrew is installed. You can install MongoDB with:"
    echo "brew tap mongodb/brew"
    echo "brew install mongodb-community"
else
    echo "MongoDB not found. Please install MongoDB to use this application."
    echo "Visit: https://www.mongodb.com/try/download/community"
fi

echo "Setup complete!"
echo ""
echo "To get started:"
echo "1. Edit the .env file with your API keys"
echo "2. Start MongoDB with: mongod --dbpath=data/db"
echo "3. Run: python -m src setup"
echo "4. Collect job listings: python -m src collect"
echo ""
echo "For more information, see the USAGE.md file."

# Deactivate virtual environment
deactivate 