"""
Main entry point for job search functionality.
"""
import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from loguru import logger
from pymongo.errors import PyMongoError

from src.database.mongodb import mongodb
from src.database.repository import job_repository
from src.processor.clustering import cluster_manager
from src.search.semantic_search import semantic_search
from src.utils.json_utils import JSONEncoder, dumps
from src.utils.logging import setup_logging


def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Job Search")
    
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Setup the database before processing",
    )
    
    # Search type arguments
    search_group = parser.add_mutually_exclusive_group(required=True)
    
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
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to return",
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Similarity threshold (0-1)",
    )
    
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )
    
    return parser.parse_args()


def format_job_listing(listing: Dict[str, Any], similarity: Optional[float] = None) -> str:
    """
    Format a job listing for text output.
    
    Args:
        listing: Job listing dictionary.
        similarity: Optional similarity score.
        
    Returns:
        Formatted string representation of the job listing.
    """
    # Extract fields
    title = listing.get("title", "No Title")
    company = listing.get("company", "Unknown Company")
    engineering_field = listing.get("engineering_field", "")
    url = listing.get("url", "")
    skills = listing.get("required_skills", [])
    
    # Format output
    result = f"\n{title} - {company}"
    
    if similarity is not None:
        result += f" (Similarity: {similarity:.2f})"
    
    result += "\n" + "=" * 80 + "\n"
    
    if engineering_field:
        result += f"Field: {engineering_field}\n"
    
    if skills:
        result += f"Skills: {', '.join(skills)}\n"
    
    if url:
        result += f"URL: {url}\n"
    
    return result


def print_search_results(
    results: List[Tuple[Dict[str, Any], float]],
    output_format: str = "text",
    query_info: str = ""
) -> None:
    """
    Print search results.
    
    Args:
        results: List of tuples (job listing, similarity score).
        output_format: Output format (text or json).
        query_info: Information about the query performed.
    """
    if not results:
        print("No results found.")
        return
    
    if output_format == "json":
        json_results = []
        for listing, similarity in results:
            json_listing = dict(listing)
            json_listing["similarity"] = similarity
            json_results.append(json_listing)
        
        print(dumps({"query": query_info, "results": json_results}, indent=2))
    else:
        print(f"\nSearch Results: {query_info}")
        print(f"Found {len(results)} matches:\n")
        
        for i, (listing, similarity) in enumerate(results):
            print(f"#{i+1} {format_job_listing(listing, similarity)}")


def search_by_cluster(cluster_id: str, limit: int = 10) -> List[Tuple[Dict[str, Any], float]]:
    """
    Search for job listings in a specific cluster.
    
    Args:
        cluster_id: ID of the cluster.
        limit: Maximum number of results to return.
        
    Returns:
        List of tuples (job listing, similarity score).
    """
    try:
        # Get cluster
        try:
            object_id = ObjectId(cluster_id)
        except Exception:
            logger.error(f"Invalid cluster ID format: {cluster_id}")
            return []
            
        cluster = cluster_manager.cluster_collection.find_one({"_id": object_id})
        
        if not cluster:
            logger.error(f"Cluster not found: {cluster_id}")
            return []
        
        # Get listings in cluster
        listing_ids = cluster.get("listing_ids", [])
        if not listing_ids:
            logger.warning(f"No listings found in cluster {cluster_id}")
            return []
        
        # Limit the number of listings
        listing_ids = listing_ids[:limit]
        
        # Get the listings
        results = []
        for listing_id in listing_ids:
            listing = job_repository.get_processed_listing(listing_id)
            if listing:
                # Use a placeholder similarity of 1.0 for cluster results
                results.append((listing, 1.0))
            else:
                logger.warning(f"Listing {listing_id} referenced in cluster {cluster_id} not found in database")
        
        if not results:
            logger.warning(f"None of the listings in cluster {cluster_id} could be retrieved")
        
        return results
        
    except PyMongoError as e:
        logger.error(f"MongoDB error searching by cluster: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error searching by cluster: {str(e)}")
        return []


def main():
    """
    Main function for the search CLI.
    """
    # Set up logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    # Set up database if requested
    if args.setup_db:
        logger.info("Setting up database")
        mongodb.setup_database()
    
    results = []
    query_info = ""
    
    # Handle search commands
    if args.query:
        logger.info(f"Searching for: {args.query}")
        results = semantic_search.search(
            query=args.query,
            limit=args.limit,
            threshold=args.threshold,
        )
        query_info = f"Text query: '{args.query}'"
    
    elif args.skills:
        skills = [s.strip() for s in args.skills.split(",")]
        logger.info(f"Searching by skills: {skills}")
        results = semantic_search.search_by_skills(
            skills=skills,
            limit=args.limit,
            threshold=args.threshold,
        )
        query_info = f"Skills: {', '.join(skills)}"
    
    elif args.company_role:
        company, role = args.company_role
        logger.info(f"Searching for {role} at {company}")
        results = semantic_search.search_by_company_and_role(
            company=company,
            role=role,
            limit=args.limit,
            threshold=args.threshold,
        )
        query_info = f"{role} at {company}"
    
    elif args.field:
        logger.info(f"Searching by field: {args.field}")
        results = semantic_search.search_by_field(
            field=args.field,
            limit=args.limit,
            threshold=args.threshold,
        )
        query_info = f"Field: {args.field}"
    
    elif args.similar_to:
        logger.info(f"Finding listings similar to: {args.similar_to}")
        results = semantic_search.find_similar_listings(
            listing_id=args.similar_to,
            limit=args.limit,
            threshold=args.threshold,
        )
        query_info = f"Similar to listing ID: {args.similar_to}"
    
    elif args.cluster:
        logger.info(f"Finding listings in cluster: {args.cluster}")
        results = search_by_cluster(
            cluster_id=args.cluster,
            limit=args.limit,
        )
        # Get cluster name for query info
        cluster = cluster_manager.cluster_collection.find_one({"_id": ObjectId(args.cluster)})
        cluster_name = cluster.get("name", "Unknown Cluster") if cluster else "Unknown Cluster"
        query_info = f"Cluster: {cluster_name} (ID: {args.cluster})"
    
    # Print results
    print_search_results(results, args.output, query_info)
    
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main()) 