"""
Command-line interface for job processor.
"""
import argparse
import sys
from typing import Optional

from loguru import logger

from src.database.mongodb import mongodb
from src.processor.clustering import cluster_manager
from src.processor.job_processor import JobProcessor
from src.utils.logging import setup_logging


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Job Listings Processor")
    
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Setup the database before processing",
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size for processing",
    )
    
    parser.add_argument(
        "--max-listings",
        type=int,
        default=None,
        help="Maximum number of listings to process",
    )
    
    parser.add_argument(
        "--listing-id",
        help="Process a specific listing by ID",
    )
    
    # Add clustering commands
    parser.add_argument(
        "--create-clusters",
        action="store_true",
        help="Create clusters from all processed job listings",
    )
    
    parser.add_argument(
        "--update-summaries",
        action="store_true",
        help="Update all cluster summaries",
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the job processor.
    """
    # Set up logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    # Set up database if requested
    if args.setup_db:
        logger.info("Setting up database")
        mongodb.setup_database()
    
    # Create processor
    processor = JobProcessor()
    
    # Process specific listing if requested
    if args.listing_id:
        logger.info(f"Processing specific listing: {args.listing_id}")
        
        # Get raw listing
        from src.database.repository import job_repository
        raw_listing = job_repository.get_raw_listing(args.listing_id)
        
        if not raw_listing:
            logger.error(f"Raw listing not found: {args.listing_id}")
            return 1
        
        # Process listing
        processed_id = processor.process_raw_listing(raw_listing)
        
        if processed_id:
            logger.info(f"Successfully processed listing: {processed_id}")
            
            # Check for duplicates
            duplicates = processor.check_for_duplicates(processed_id)
            if duplicates:
                logger.warning(f"Found potential duplicates: {duplicates}")
            
            return 0
        else:
            logger.error(f"Failed to process listing: {args.listing_id}")
            return 1
    
    # Create clusters if requested
    elif args.create_clusters:
        logger.info("Creating job listing clusters")
        cluster_ids = cluster_manager.create_clusters()
        
        if cluster_ids:
            logger.info(f"Successfully created {len(cluster_ids)} clusters")
            return 0
        else:
            logger.warning("No clusters created")
            return 1
    
    # Update cluster summaries if requested
    elif args.update_summaries:
        logger.info("Updating cluster summaries")
        updated_count = cluster_manager.update_cluster_summaries()
        
        if updated_count > 0:
            logger.info(f"Successfully updated {updated_count} cluster summaries")
            return 0
        else:
            logger.warning("No cluster summaries updated")
            return 1
    
    # Process in batch otherwise
    else:
        logger.info("Processing job listings in batch")
        
        # Process batch
        processed_count, total_count = processor.process_batch(
            batch_size=args.batch_size,
        )
        
        if total_count == 0:
            logger.warning("No listings to process")
            return 0
        
        logger.info(f"Processed {processed_count} of {total_count} listings")
        
        # Continue with additional batches if requested
        if args.max_listings and args.max_listings > processed_count:
            remaining = args.max_listings - processed_count
            logger.info(f"Processing {remaining} more listings")
            
            additional_processed, additional_total = processor.process_all(
                max_listings=remaining,
            )
            
            processed_count += additional_processed
            total_count += additional_total
            
            logger.info(f"Total processed: {processed_count} of {total_count} listings")
        
        return 0


if __name__ == "__main__":
    sys.exit(main()) 