"""
Command-line interface for cluster management.
"""
import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from bson import ObjectId
from loguru import logger
from pymongo.errors import PyMongoError

from src.database.mongodb import mongodb
from src.processor.clustering import cluster_manager
from src.utils.json_utils import JSONEncoder, dumps
from src.utils.logging import setup_logging


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Job Clusters Manager")
    
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Setup the database before processing",
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all clusters",
    )
    
    parser.add_argument(
        "--get-summary",
        metavar="CLUSTER_ID",
        help="Get summary for a specific cluster",
    )
    
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )
    
    return parser.parse_args()


def list_clusters(output_format: str = "text") -> int:
    """
    List all job clusters.
    
    Args:
        output_format: Output format (text or json).
        
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        # Get all clusters
        clusters = list(cluster_manager.cluster_collection.find({}).sort("size", -1))
        
        if not clusters:
            logger.warning("No clusters found")
            return 0
        
        # Output in requested format
        if output_format == "json":
            print(dumps(clusters, indent=2))
        else:
            # Text format
            print(f"\nFound {len(clusters)} job clusters:\n")
            print(f"{'ID':<24} {'Name':<40} {'Size':<8} {'Created':<22}")
            print("-" * 95)
            
            for cluster in clusters:
                cluster_id = str(cluster["_id"])
                name = cluster.get("name", "Unknown")
                size = cluster.get("size", 0)
                created_at = cluster.get("created_at", "").strftime("%Y-%m-%d %H:%M:%S") if cluster.get("created_at") else "Unknown"
                
                print(f"{cluster_id:<24} {name[:40]:<40} {size:<8} {created_at:<22}")
        
        return 0
        
    except PyMongoError as e:
        logger.error(f"MongoDB error listing clusters: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Error listing clusters: {str(e)}")
        return 1


def get_cluster_summary(cluster_id: str, output_format: str = "text") -> int:
    """
    Get and display summary for a cluster.
    
    Args:
        cluster_id: ID of the cluster.
        output_format: Output format (text or json).
        
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        # Get cluster
        try:
            object_id = ObjectId(cluster_id)
        except Exception:
            logger.error(f"Invalid cluster ID format: {cluster_id}")
            return 1
            
        cluster = cluster_manager.cluster_collection.find_one({"_id": object_id})
        
        if not cluster:
            logger.error(f"Cluster not found: {cluster_id}")
            return 1
        
        # Get summary
        summary = cluster_manager.get_cluster_summary(cluster_id)
        
        if not summary:
            # No summary exists, generate one
            logger.info(f"No summary found for cluster {cluster_id}, generating...")
            summary_id = cluster_manager._generate_cluster_summary(cluster_id)
            
            if summary_id:
                summary = cluster_manager.get_cluster_summary(cluster_id)
            
            if not summary:
                logger.error(f"Failed to generate summary for cluster {cluster_id}")
                return 1
        
        # Output in requested format
        if output_format == "json":
            result = {
                "cluster": cluster,
                "summary": summary
            }
            print(dumps(result, indent=2))
        else:
            # Text format
            metadata = cluster.get("metadata", {})
            name = cluster.get("name", "Unknown Cluster")
            size = cluster.get("size", 0)
            
            print(f"\n{name} (ID: {cluster_id})")
            print("=" * 80)
            print(f"Size: {size} job listings")
            
            if "common_field" in metadata and metadata["common_field"]:
                print(f"Field: {metadata['common_field']}")
            
            if "common_companies" in metadata and metadata["common_companies"]:
                print(f"Companies: {', '.join(metadata['common_companies'])}")
            
            if "common_skills" in metadata and metadata["common_skills"]:
                print(f"Common Skills: {', '.join(metadata['common_skills'])}")
            
            print("\nSummary:")
            print("-" * 80)
            print(summary.get("summary", "No summary available."))
            print("-" * 80)
            
            # Show sample listings
            listing_ids = cluster.get("listing_ids", [])
            if listing_ids:
                print(f"\nSample Job Listings (showing 3 of {len(listing_ids)}):")
                
                from src.database.repository import job_repository
                for i, listing_id in enumerate(listing_ids[:3]):
                    listing = job_repository.get_processed_listing(listing_id)
                    if listing:
                        print(f"\n{i+1}. {listing.get('title', 'Unknown')} - {listing.get('company', 'Unknown')}")
                        print(f"   URL: {listing.get('url', 'N/A')}")
        
        return 0
        
    except PyMongoError as e:
        logger.error(f"MongoDB error getting cluster summary: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Error getting cluster summary: {str(e)}")
        return 1


def main():
    """
    Main function for the clusters CLI.
    """
    # Set up logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    # Set up database if requested
    if args.setup_db:
        logger.info("Setting up database")
        mongodb.setup_database()
    
    # Handle commands
    if args.list:
        return list_clusters(args.output)
    
    elif args.get_summary:
        return get_cluster_summary(args.get_summary, args.output)
    
    else:
        logger.error("No cluster command specified. Use --list or --get-summary.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 