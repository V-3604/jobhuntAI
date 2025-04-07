"""
Main entry point for job collector.
"""
import argparse
import sys
from typing import Optional

from loguru import logger

from src.collector.job_collector import job_collector
from src.database.mongodb import mongodb
from src.utils.logging import setup_logging


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Job listing collector")
    
    parser.add_argument(
        "--type",
        choices=["companies", "fields", "all"],
        default="all",
        help="Type of collection to run (companies, fields, or all)",
    )
    
    parser.add_argument(
        "--specific",
        help="Specific company or field to collect (if type is companies or fields)",
    )
    
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Set up the database before collecting",
    )
    
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Maximum results per query",
    )
    
    return parser.parse_args()


def main():
    """
    Main function for job collector.
    """
    # Set up logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    try:
        # Set up database if requested
        if args.setup_db:
            logger.info("Setting up database")
            mongodb.setup_database()
        
        # Override max results if provided
        if args.max_results is not None:
            job_collector.max_results_per_query = args.max_results
            logger.info(f"Set max results per query to {args.max_results}")
        
        # Run collector based on type
        if args.type == "companies":
            if args.specific:
                # Collect for specific company
                logger.info(f"Collecting jobs for company: {args.specific}")
                listing_ids = job_collector.collect_company_jobs(args.specific)
                logger.info(f"Collected {len(listing_ids)} job listings")
            else:
                # Collect for all companies
                logger.info("Collecting jobs for all companies")
                results = job_collector.collect_all_companies()
                total = sum(len(ids) for ids in results.values())
                logger.info(f"Collected {total} job listings from {len(results)} companies")
        
        elif args.type == "fields":
            if args.specific:
                # Collect for specific field
                logger.info(f"Collecting jobs for field: {args.specific}")
                listing_ids = job_collector.collect_field_jobs(args.specific)
                logger.info(f"Collected {len(listing_ids)} job listings")
            else:
                # Collect for all fields
                logger.info("Collecting jobs for all fields")
                results = job_collector.collect_all_fields()
                total = sum(len(ids) for ids in results.values())
                logger.info(f"Collected {total} job listings from {len(results)} fields")
        
        else:  # all
            # Collect for all companies and fields
            logger.info("Collecting jobs for all companies and fields")
            company_results, field_results = job_collector.collect_all()
            
            company_total = sum(len(ids) for ids in company_results.values())
            field_total = sum(len(ids) for ids in field_results.values())
            
            logger.info(
                f"Collection complete: {company_total} company listings, "
                f"{field_total} field listings"
            )
        
        logger.info("Job collection completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error during job collection: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 