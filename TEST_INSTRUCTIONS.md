# Science & Engineering Job Database - Testing Instructions

This document provides step-by-step instructions for testing the Job Database system functionality.

## Prerequisites Setup

Before running the tests, ensure that you have:

1. Installed all dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env`:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_CSE_ID=your_google_cse_id
   ```

3. Started MongoDB:
   ```bash
   mongod --dbpath=data/db
   ```

## Test 1: Basic Database Setup

First, let's test the database setup functionality:

```bash
# Initialize the database
python -m src setup

# Verify output indicates successful database setup
```

## Test 2: Collecting Job Listings

Test the collection of job listings:

```bash
# Collect a small batch of job listings from a specific company
python -m src collect --type companies --specific "Google" --max-results 3

# Verify that the listings were collected successfully
# The output should show information about the successful collection
```

## Test 3: Processing Job Listings

Test processing the collected job listings:

```bash
# Process the collected job listings
python -m src process --batch-size 3

# Verify that processing was successful
# The output should indicate how many listings were processed
```

## Test 4: Creating and Managing Clusters

Test the clustering functionality:

```bash
# Create clusters from the processed listings
python -m src cluster --create

# List all clusters
python -m src cluster --list

# Get a detailed summary of a specific cluster (use an ID from the list)
python -m src cluster --get-summary "cluster_id_here"

# Verify that clusters were created and can be viewed
```

## Test 5: Searching for Jobs

Test the search functionality:

```bash
# Basic text search
python -m src search --query "software engineer"

# Search by skills
python -m src search --skills "python,machine learning"

# Search by engineering field
python -m src search --field "Software Engineering"

# Search within a specific cluster (use an ID from Test 4)
python -m src search --cluster "cluster_id_here"

# Verify that search results are relevant and correctly formatted
```

## Test 6: Database Maintenance

Test the database maintenance functionality:

```bash
# Get database statistics
python -m src update --stats

# Mark expired listings (might not have effect if listings are new)
python -m src update --mark-expired

# Find and mark duplicates
python -m src update --remove-duplicates

# Maintain the maximum listing count
python -m src update --maintain-count

# Verify that the operations complete without errors
```

## Test 7: Full Update Process

Test the complete daily update process:

```bash
# Run the daily update
python -m src update --daily

# Verify that the update completes successfully
# The output should show a summary of the actions performed
```

## Test 8: End-to-End Workflow

Test the end-to-end workflow:

```bash
# 1. Start with a fresh database setup
python -m src setup

# 2. Collect job listings
python -m src collect --max-results 10

# 3. Process job listings
python -m src process

# 4. Create clusters
python -m src cluster --create

# 5. Search for relevant jobs
python -m src search --query "software engineering internship"

# 6. Get database statistics
python -m src update --stats

# Verify that each step completes successfully and the final
# search returns relevant results
```

## Test 9: Scheduled Updates

Test setting up scheduled updates:

```bash
# Set up a scheduled update (note: this modifies your crontab)
./scripts/setup_scheduled_updates.sh "*/5 * * * *"  # Run every 5 minutes for testing

# Check that the cron job was created
crontab -l | grep daily_update

# After waiting for the scheduled time:
# Check logs in the logs directory for scheduled execution
```

## Test 10: Performance Testing

For performance testing with larger datasets:

```bash
# Collect a larger dataset
python -m src collect --max-results 50

# Process the dataset in multiple batches
python -m src process --batch-size 10

# Test search performance
time python -m src search --query "software engineering"

# Test clustering performance
time python -m src cluster --create
```

## Troubleshooting

If you encounter issues during testing:

1. Check the `logs` directory for detailed log files
2. Verify MongoDB is running with `pgrep mongod`
3. Check API key validity with simple test calls
4. Review the `.env` file for any configuration errors
5. Ensure the Python environment is correctly activated

## Expected Results

After completing all tests successfully:

1. The database should contain job listings from the specified sources
2. Listings should be processed with extracted skills and metadata
3. Listings should be organized into meaningful clusters
4. Search functionality should return relevant results
5. Database maintenance should keep the system in an optimal state

Each test should complete without errors, and the system should maintain consistent behavior across all operations. 