"""
Command-line interface for the updater module.
"""
import argparse
import json
import sys
from typing import Any, Dict

from bson import ObjectId
from loguru import logger

from src.database.mongodb import mongodb
from src.updater.update_manager import update_manager
from src.utils.json_utils import JSONEncoder
from src.utils.logging import setup_logging


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Job Database Updater")
    
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Setup the database before processing",
    )
    
    parser.add_argument(
        "--daily-update",
        action="store_true",
        help="Perform a daily update of the job database",
    )
    
    parser.add_argument(
        "--mark-expired",
        action="store_true",
        help="Mark expired job listings",
    )
    
    parser.add_argument(
        "--remove-duplicates",
        action="store_true",
        help="Find and mark duplicate job listings",
    )
    
    parser.add_argument(
        "--maintain-count",
        action="store_true",
        help="Maintain the maximum number of job listings",
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Get database statistics",
    )
    
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )
    
    return parser.parse_args()


def print_stats(stats: Dict[str, Any], output_format: str = "text") -> None:
    """
    Print database statistics.
    
    Args:
        stats: Statistics dictionary.
        output_format: Output format (text or json).
    """
    if output_format == "json":
        from src.utils.json_utils import dumps
        print(dumps(stats, indent=2))
    else:
        print("\nJob Database Statistics")
        print("=" * 50)
        print(f"Raw Listings: {stats.get('raw_listings', 0)}")
        print(f"Processed Listings: {stats.get('processed_listings', 0)}")
        print(f"Active Listings: {stats.get('active_listings', 0)}")
        print(f"Expired Listings: {stats.get('expired_listings', 0)}")
        print(f"Duplicate Listings: {stats.get('duplicate_listings', 0)}")
        print(f"Clusters: {stats.get('clusters', 0)}")
        
        if stats.get('newest_listing_date'):
            print(f"Newest Listing: {stats['newest_listing_date'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if stats.get('oldest_listing_date'):
            print(f"Oldest Listing: {stats['oldest_listing_date'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"Generated: {stats.get('generated_at', 'N/A').strftime('%Y-%m-%d %H:%M:%S')}")


def print_update_report(report: Dict[str, Any], output_format: str = "text") -> None:
    """
    Print update report.
    
    Args:
        report: Update report dictionary.
        output_format: Output format (text or json).
    """
    if output_format == "json":
        from src.utils.json_utils import dumps
        print(dumps(report, indent=2))
    else:
        print("\nJob Database Update Report")
        print("=" * 50)
        print(f"Update Time: {report.get('update_time', 'N/A').strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Expired Listings: {report.get('expired_count', 0)}")
        print(f"Duplicate Listings: {report.get('duplicate_count', 0)}")
        print(f"Collected Listings: {report.get('collected_count', 0)}")
        print(f"Processed Listings: {report.get('processed_count', 0)}")
        print(f"Clusters Created: {report.get('cluster_count', 0)}")
        print(f"Summaries Updated: {report.get('summary_count', 0)}")
        print(f"Listings Removed: {report.get('removed_count', 0)}")
        print(f"Current Active Listings: {report.get('current_active_listings', 0)}")
        
        # Print stats if available
        if "database_stats" in report and report["database_stats"]:
            print("\nDatabase Statistics:")
            print("-" * 50)
            stats = report["database_stats"]
            print(f"Raw Listings: {stats.get('raw_listings', 0)}")
            print(f"Processed Listings: {stats.get('processed_listings', 0)}")
            print(f"Active Listings: {stats.get('active_listings', 0)}")
            print(f"Clusters: {stats.get('clusters', 0)}")


def main():
    """
    Main function for the updater CLI.
    """
    # Set up logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    # Set up database if requested
    if args.setup_db:
        logger.info("Setting up database")
        mongodb.setup_database()
    
    # Check if any update command was specified
    command_specified = any([
        args.daily_update,
        args.mark_expired,
        args.remove_duplicates,
        args.maintain_count,
        args.stats
    ])
    
    if not command_specified:
        logger.error("No update command specified. Use --help to see available commands.")
        return 1
    
    # Handle commands
    if args.daily_update:
        logger.info("Performing daily update")
        report = update_manager.perform_daily_update()
        print_update_report(report, args.output)
        return 0
    
    if args.mark_expired:
        logger.info("Marking expired listings")
        expired_count = update_manager.mark_expired_listings()
        
        if args.output == "json":
            print(json.dumps({"expired_count": expired_count}, indent=2))
        else:
            print(f"\nMarked {expired_count} job listings as expired")
    
    if args.remove_duplicates:
        logger.info("Removing duplicates")
        duplicate_count = update_manager.remove_duplicates()
        
        if args.output == "json":
            print(json.dumps({"duplicate_count": duplicate_count}, indent=2))
        else:
            print(f"\nMarked {duplicate_count} duplicate job listings")
    
    if args.maintain_count:
        logger.info("Maintaining listing count")
        removed_count, current_count = update_manager.maintain_listing_count()
        
        if args.output == "json":
            print(json.dumps({
                "removed_count": removed_count,
                "current_count": current_count
            }, indent=2))
        else:
            print(f"\nRemoved {removed_count} old listings to maintain database size")
            print(f"Current active listing count: {current_count}")
    
    if args.stats:
        logger.info("Getting database statistics")
        stats = update_manager.get_database_stats()
        print_stats(stats, args.output)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 