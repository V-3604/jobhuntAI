# Science & Engineering Job Database - Usage Guide

This guide explains how to use the Science & Engineering Job Database system for collecting, processing, and searching for job listings.

## Prerequisites

Before using the system, make sure you have:

1. Python 3.10+ installed
2. MongoDB installed and running
3. API keys for:
   - OpenAI API
   - Google Programmable Search Engine API

## Setup

1. Clone the repository and navigate to the project directory
2. Run the setup script:
   ```bash
   ./scripts/setup.sh
   ```
3. Edit the `.env` file with your API keys and configuration
4. Start MongoDB:
   ```bash
   mongod --dbpath=data/db
   ```
5. Set up the database:
   ```bash
   python -m src setup
   ```

## Basic Commands

The system has a command-line interface with several main commands:

```bash
# General syntax
python -m src COMMAND [OPTIONS]
```

Available commands:
- `setup`: Initialize the database
- `collect`: Collect job listings
- `process`: Process raw job listings
- `cluster`: Manage job clusters
- `update`: Update the database
- `search`: Search for job listings

## Collecting Job Listings

Collect job listings from companies and engineering fields:

```bash
# Collect from all sources
python -m src collect

# Collect only from companies
python -m src collect --type companies

# Collect only from a specific company
python -m src collect --type companies --specific "Google"

# Collect only for a specific engineering field
python -m src collect --type fields --specific "Software Engineering"

# Limit results per query
python -m src collect --max-results 5
```

## Processing Job Listings

Process the collected raw job listings:

```bash
# Process all unprocessed listings
python -m src process

# Process with a specific batch size
python -m src process --batch-size 5

# Process a maximum number of listings
python -m src process --max-listings 20

# Process a specific listing by ID
python -m src process --listing-id "listing_id_here"
```

## Managing Clusters

The system automatically clusters similar job listings for easier exploration:

```bash
# Create clusters from processed job listings
python -m src cluster --create

# Update summaries for all clusters
python -m src cluster --update-summaries

# List all clusters
python -m src cluster --list

# Get detailed summary for a specific cluster
python -m src cluster --get-summary "cluster_id_here"

# Output cluster information in JSON format
python -m src cluster --list --output json
```

## Updating the Database

Maintain the database with automatic updates:

```bash
# Perform a daily update (collect, process, cluster, and maintain)
python -m src update --daily

# Mark expired job listings
python -m src update --mark-expired

# Find and mark duplicate job listings
python -m src update --remove-duplicates

# Maintain maximum number of job listings
python -m src update --maintain-count

# Get database statistics
python -m src update --stats

# Output update information in JSON format
python -m src update --stats --output json
```

You can also set up automatic daily updates using the provided script:

```bash
# Set up daily updates at the default time (2:00 AM)
./scripts/setup_scheduled_updates.sh

# Set up daily updates at a custom time (e.g., 4:00 AM)
./scripts/setup_scheduled_updates.sh "0 4 * * *"
```

## Searching for Jobs

Search the processed job listings:

```bash
# Free text search
python -m src search --query "machine learning intern"

# Search by skills
python -m src search --skills "python,machine learning,data analysis"

# Search by company and role
python -m src search --company-role "Google" "Software Engineer"

# Search by engineering field
python -m src search --field "Software Engineering"

# Find similar listings
python -m src search --similar-to "listing_id_here"

# Search within a specific cluster
python -m src search --cluster "cluster_id_here"

# Limit number of results
python -m src search --query "data science" --limit 5

# Set similarity threshold
python -m src search --query "robotics" --threshold 0.8

# Output in JSON format
python -m src search --query "AI engineer" --output json
```

## Example Workflow

Here's a typical workflow:

```bash
# 1. Set up the database
python -m src setup

# 2. Collect job listings from all sources
python -m src collect

# 3. Process the collected listings
python -m src process

# 4. Create clusters of similar job listings
python -m src cluster --create

# 5. Search for relevant jobs
python -m src search --skills "python,machine learning,tensorflow"

# 6. Explore job clusters
python -m src cluster --list
python -m src search --cluster "cluster_id_here"

# 7. Set up automatic daily updates
./scripts/setup_scheduled_updates.sh
```

## Debugging

If you encounter issues:

1. Check the log files in the `logs` directory
2. Verify MongoDB is running correctly
3. Ensure API keys are correctly set in the `.env` file
4. If OpenAI API calls are failing, check rate limiting and quotas
5. If Google API calls are failing, verify the Custom Search Engine is set up correctly
6. Check database statistics with `python -m src update --stats`

## Configuration

The system configuration is stored in:
- `.env` file: API keys and environment-specific settings
- `config/config.yaml`: General application settings

You can modify these files to adjust the system behavior.

## API Rate Limiting

Both OpenAI and Google APIs have rate limits:

- OpenAI: Default is 100 requests per minute (RPM)
- Google CSE: Default is 60 requests per minute (RPM)

You can adjust these limits in the `.env` file based on your API tier.

## API Key Setup

### OpenAI API
1. Create an account at https://platform.openai.com/
2. Generate an API key from your account dashboard
3. Add the key to your `.env` file as `OPENAI_API_KEY`

### Google Programmable Search Engine
1. Create a project in Google Cloud Console
2. Enable the Custom Search API
3. Create an API key and add it to your `.env` file as `GOOGLE_API_KEY`
4. Create a Custom Search Engine at https://programmablesearchengine.google.com/
5. Get the Search Engine ID and add it to your `.env` file as `GOOGLE_CSE_ID`

## System Architecture

The system is structured into several modules:

1. **Collection Module**: Collects job listings from various sources
2. **Processing Module**: Analyzes and structures job listings data
3. **Clustering Module**: Groups similar job listings into clusters
4. **Search Module**: Provides semantic search capabilities
5. **Update Module**: Manages database maintenance and updates

Each module can be used independently or as part of the overall workflow. 