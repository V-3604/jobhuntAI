"""
Main entry point for the job database application.
"""
import argparse
import subprocess
import sys
from typing import Optional, List

from loguru import logger

from src.database.mongodb import mongodb
from src.utils.logging import setup_logging


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Science & Engineering Job Database")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up the database")
    
    # Collect command
    collect_parser = subparsers.add_parser("collect", help="Collect job listings")
    collect_parser.add_argument(
        "--type",
        choices=["companies", "fields", "all"],
        default="all",
        help="Type of collection to run",
    )
    collect_parser.add_argument(
        "--specific",
        help="Specific company or field to collect",
    )
    collect_parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Maximum results per query",
    )
    
    # Process command
    process_parser = subparsers.add_parser("process", help="Process job listings")
    process_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for processing",
    )
    process_parser.add_argument(
        "--max-listings",
        type=int,
        default=None,
        help="Maximum number of listings to process",
    )
    process_parser.add_argument(
        "--listing-id",
        help="Process a specific listing by ID",
    )
    
    # Cluster command
    cluster_parser = subparsers.add_parser("cluster", help="Manage job clusters")
    cluster_parser.add_argument(
        "--create",
        action="store_true",
        help="Create clusters from processed listings",
    )
    cluster_parser.add_argument(
        "--update-summaries",
        action="store_true",
        help="Update all cluster summaries",
    )
    cluster_parser.add_argument(
        "--list",
        action="store_true",
        help="List all clusters",
    )
    cluster_parser.add_argument(
        "--get-summary",
        metavar="CLUSTER_ID",
        help="Get summary for a specific cluster",
    )
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update job database")
    update_parser.add_argument(
        "--daily",
        action="store_true",
        help="Perform daily update (collect, process, cluster, and maintain)",
    )
    update_parser.add_argument(
        "--mark-expired",
        action="store_true",
        help="Mark expired job listings",
    )
    update_parser.add_argument(
        "--remove-duplicates",
        action="store_true",
        help="Find and mark duplicate job listings",
    )
    update_parser.add_argument(
        "--maintain-count",
        action="store_true",
        help="Maintain the maximum number of job listings",
    )
    update_parser.add_argument(
        "--stats",
        action="store_true",
        help="Get database statistics",
    )
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search job listings")
    
    # Search type arguments
    search_group = search_parser.add_mutually_exclusive_group(required=True)
    
    search_group.add_argument(
        "--query",
        help="Free text search query",
    )
    
    search_group.add_argument(
        "--skills",
        help="Search by skills (comma-separated)",
    )
    
    search_group.add_argument(
        "--company-role",
        nargs=2,
        metavar=("COMPANY", "ROLE"),
        help="Search by company and role",
    )
    
    search_group.add_argument(
        "--field",
        help="Search by engineering field",
    )
    
    search_group.add_argument(
        "--similar-to",
        help="Find listings similar to this listing ID",
    )
    
    search_group.add_argument(
        "--cluster",
        metavar="CLUSTER_ID",
        help="Find listings in a specific cluster",
    )
    
    # Additional search arguments
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to return",
    )
    
    search_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Similarity threshold (0-1)",
    )
    
    search_parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )
    
    return parser.parse_args()


def run_command(module_name: str, args: List[str]) -> int:
    """
    Run a command as a subprocess.
    
    Args:
        module_name: Python module name to run.
        args: Command line arguments.
        
    Returns:
        Exit code from the command.
    """
    cmd = [sys.executable, "-m", module_name] + args
    logger.debug(f"Running command: {' '.join(cmd)}")
    
    try:
        process = subprocess.run(cmd, check=True)
        return process.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        return e.returncode


def setup_database():
    """
    Set up the MongoDB database.
    
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        logger.info("Setting up database")
        mongodb.setup_database()
        logger.info("Database setup complete")
        return 0
    except Exception as e:
        logger.error(f"Database setup failed: {str(e)}")
        return 1


def main():
    """
    Main function for the job database application.
    """
    # Set up logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    if not args.command:
        logger.error("No command specified. Use --help to see available commands.")
        return 1
    
    # Handle commands
    if args.command == "setup":
        return setup_database()
    
    elif args.command == "collect":
        # Prepare arguments for collect command
        collect_args = ["--setup-db"]
        
        if args.type:
            collect_args.extend(["--type", args.type])
        
        if args.specific:
            collect_args.extend(["--specific", args.specific])
        
        if args.max_results:
            collect_args.extend(["--max-results", str(args.max_results)])
        
        return run_command("src.collector", collect_args)
    
    elif args.command == "process":
        # Prepare arguments for process command
        process_args = ["--setup-db"]
        
        if args.batch_size:
            process_args.extend(["--batch-size", str(args.batch_size)])
        
        if args.max_listings:
            process_args.extend(["--max-listings", str(args.max_listings)])
        
        if args.listing_id:
            process_args.extend(["--listing-id", args.listing_id])
        
        return run_command("src.processor", process_args)
    
    elif args.command == "cluster":
        # Prepare arguments for cluster command
        cluster_args = ["--setup-db"]
        
        if args.create:
            cluster_args.append("--create-clusters")
        
        if args.update_summaries:
            cluster_args.append("--update-summaries")
        
        if args.list or args.get_summary:
            # These will be handled by a new module we need to create
            if args.list:
                cluster_args.append("--list")
            
            if args.get_summary:
                cluster_args.extend(["--get-summary", args.get_summary])
            
            return run_command("src.clusters", cluster_args)
        
        # Use the processor module for create and update commands
        return run_command("src.processor", cluster_args)
    
    elif args.command == "update":
        # Prepare arguments for update command
        update_args = ["--setup-db"]
        
        if args.daily:
            update_args.append("--daily-update")
        
        if args.mark_expired:
            update_args.append("--mark-expired")
        
        if args.remove_duplicates:
            update_args.append("--remove-duplicates")
        
        if args.maintain_count:
            update_args.append("--maintain-count")
        
        if args.stats:
            update_args.append("--stats")
        
        # Add output format if provided
        if hasattr(args, "output") and args.output:
            update_args.extend(["--output", args.output])
        
        return run_command("src.updater", update_args)
    
    elif args.command == "search":
        # Prepare arguments for search command
        search_args = ["--setup-db"]
        
        if args.query:
            search_args.extend(["--query", args.query])
        
        elif args.skills:
            search_args.extend(["--skills", args.skills])
        
        elif args.company_role:
            search_args.extend(["--company-role", args.company_role[0], args.company_role[1]])
        
        elif args.field:
            search_args.extend(["--field", args.field])
        
        elif args.similar_to:
            search_args.extend(["--similar-to", args.similar_to])
        
        elif args.cluster:
            search_args.extend(["--cluster", args.cluster])
        
        if args.limit:
            search_args.extend(["--limit", str(args.limit)])
        
        if args.threshold:
            search_args.extend(["--threshold", str(args.threshold)])
        
        if args.output:
            search_args.extend(["--output", args.output])
        
        return run_command("src.search", search_args)
    
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 