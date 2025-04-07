# Science & Engineering Job Database

A comprehensive job database system for science and engineering undergraduates, designed to help students find relevant internships and entry-level positions.

## Overview

This system collects job listings from top tech companies and engineering firms, processes them using AI to extract valuable information, and provides powerful search capabilities to find the most relevant opportunities based on skills, interests, and career goals.

Key features:
- **Smart Collection**: Automatically collects job listings from company career pages and other sources
- **AI Processing**: Uses OpenAI (GPT-4) to extract skills, categorize jobs, and create searchable data
- **Intelligent Clustering**: Groups similar job listings to identify trends and patterns
- **Semantic Search**: Find jobs by skills, companies, fields, or similarity to other listings
- **Automatic Updates**: Maintains up-to-date information through scheduled updates

## System Requirements

- Python 3.10+
- MongoDB 6.0+
- OpenAI API key
- Google Programmable Search Engine API key and Custom Search Engine ID

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/jobhuntAI.git
   cd jobhuntAI
   ```

2. **Run the setup script**:
   ```bash
   ./scripts/setup.sh
   ```

3. **Edit the `.env` file** with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_CSE_ID=your_google_cse_id
   ```

4. **Set up the database**:
   ```bash
   python -m src setup
   ```

5. **Collect job listings**:
   ```bash
   python -m src collect
   ```

6. **Process the listings**:
   ```bash
   python -m src process
   ```

7. **Create clusters**:
   ```bash
   python -m src cluster --create
   ```

8. **Search for job listings**:
   ```bash
   python -m src search --query "machine learning internship"
   ```

## Core Modules

The system consists of several core modules:

### Collection Module
Collects job listings from Google search results and company career pages.

```bash
# Collect jobs from all configured sources
python -m src collect

# Collect jobs only from specific companies
python -m src collect --type companies --specific "Google"

# Collect jobs for specific fields
python -m src collect --type fields --specific "Software Engineering"
```

### Processing Module
Processes raw job listings using OpenAI to extract structured data.

```bash
# Process all unprocessed listings
python -m src process

# Process with specific batch size
python -m src process --batch-size 10
```

### Clustering Module
Groups similar jobs into clusters and generates summaries.

```bash
# Create clusters
python -m src cluster --create

# List all clusters
python -m src cluster --list

# Get detailed summary of a cluster
python -m src cluster --get-summary "cluster_id"
```

### Search Module
Provides semantic search capabilities for finding relevant jobs.

```bash
# Search by text query
python -m src search --query "data science internship"

# Search by skills
python -m src search --skills "python,machine learning,tensorflow"

# Search by engineering field
python -m src search --field "Software Engineering"

# Search within a specific cluster
python -m src search --cluster "cluster_id"
```

### Update Module
Manages database maintenance and automated updates.

```bash
# Perform daily update
python -m src update --daily

# Get database statistics
python -m src update --stats

# Set up scheduled updates
./scripts/setup_scheduled_updates.sh
```

## Configuration

The system configuration is managed in two main files:

- `.env`: Contains API keys and environment-specific configuration
- `config/config.yaml`: Contains general application settings

## Documentation

- [Usage Guide](USAGE.md): Detailed usage instructions
- [Implementation Details](IMPLEMENTATION.md): System architecture and design
- [Testing Instructions](TEST_INSTRUCTIONS.md): Step-by-step testing guide

## Data Sources

The system collects job listings from:

1. Major tech companies (Google, Microsoft, Apple, Amazon, etc.)
2. Engineering firms (Boeing, Lockheed Martin, etc.)
3. Research institutions (NASA, National Labs, etc.)
4. Engineering-focused job boards and career pages

## License

[MIT License](LICENSE)

## Acknowledgements

This project was developed using:
- OpenAI API for text processing and embeddings
- Google Programmable Search Engine API for job listing collection
- MongoDB for data storage
- Various Python libraries (PyMongo, requests, BeautifulSoup, scikit-learn, etc.)