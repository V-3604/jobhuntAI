"""
Intelligent update manager for job listings.

This module handles updating job listings, tracking expiration,
and maintaining the database with up-to-date entries.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger
from pymongo.errors import PyMongoError

from src.collector.job_collector import job_collector
from src.database.mongodb import mongodb
from src.database.repository import job_repository
from src.processor.clustering import cluster_manager
from src.processor.job_processor import JobProcessor
from src.utils.config import config


class UpdateManager:
    """
    Manager for handling job listing updates.
    
    This class handles the intelligent updating of the job database,
    including expiration tracking, duplicate management, and daily updates.
    """
    
    def __init__(self):
        """Initialize the update manager."""
        self.repository = job_repository
        self.collector = job_collector
        self.processor = JobProcessor()
        self.cluster_manager = cluster_manager
        
        # Get configuration
        self.ttl_days = config["database"].get("job_ttl_days", 30)
        self.max_listings = config.get("updater", {}).get("max_listings", 1000)
        self.duplicate_similarity_threshold = config.get("updater", {}).get("duplicate_threshold", 0.9)
        
        # Collections
        self.processed_collection = mongodb.get_collection("processed_listings")
        
        logger.info(f"Update manager initialized with TTL of {self.ttl_days} days and max {self.max_listings} listings")
    
    def mark_expired_listings(self) -> int:
        """
        Mark old listings as expired.
        
        Returns:
            Number of listings marked as expired.
        """
        try:
            # Calculate expiration date
            expiration_date = datetime.utcnow() - timedelta(days=self.ttl_days)
            
            # Find listings older than expiration date and not already marked expired
            result = self.processed_collection.update_many(
                {
                    "created_at": {"$lt": expiration_date},
                    "$or": [
                        {"expired": {"$exists": False}},
                        {"expired": False}
                    ]
                },
                {"$set": {"expired": True, "updated_at": datetime.utcnow()}}
            )
            
            expired_count = result.modified_count
            logger.info(f"Marked {expired_count} job listings as expired")
            return expired_count
            
        except Exception as e:
            logger.error(f"Error marking expired listings: {str(e)}")
            return 0
    
    def remove_duplicates(self) -> int:
        """
        Find and mark duplicate listings.
        
        Returns:
            Number of duplicates marked.
        """
        try:
            # Get all non-expired processed listings
            listings = list(self.processed_collection.find(
                {"$or": [{"expired": {"$exists": False}}, {"expired": False}]}
            ))
            
            # Track duplicates
            duplicate_count = 0
            checked_pairs = set()
            
            # Process each listing
            for i, listing in enumerate(listings):
                listing_id = str(listing["_id"])
                
                # Skip if already marked as a duplicate
                if listing.get("is_duplicate", False):
                    continue
                
                # Check for duplicates
                duplicates = self.processor.check_for_duplicates(
                    listing_id, 
                    threshold=self.duplicate_similarity_threshold
                )
                
                # Mark duplicates
                for dup_id in duplicates:
                    # Skip if already checked this pair
                    pair_key = tuple(sorted([listing_id, dup_id]))
                    if pair_key in checked_pairs:
                        continue
                    
                    checked_pairs.add(pair_key)
                    
                    # Get the duplicate listing
                    dup_listing = self.repository.get_processed_listing(dup_id)
                    if not dup_listing:
                        continue
                    
                    # Determine which one to keep (newer one)
                    original_date = listing.get("created_at", datetime.min)
                    dup_date = dup_listing.get("created_at", datetime.min)
                    
                    # Mark the older one as duplicate
                    if original_date >= dup_date:
                        # Original is newer, mark duplicate as duplicate of original
                        self.repository.update_processed_listing(
                            dup_id,
                            {
                                "is_duplicate": True,
                                "duplicate_of": listing_id,
                                "updated_at": datetime.utcnow()
                            }
                        )
                    else:
                        # Duplicate is newer, mark original as duplicate of duplicate
                        self.repository.update_processed_listing(
                            listing_id,
                            {
                                "is_duplicate": True,
                                "duplicate_of": dup_id,
                                "updated_at": datetime.utcnow()
                            }
                        )
                    
                    duplicate_count += 1
            
            logger.info(f"Marked {duplicate_count} duplicate job listings")
            return duplicate_count
            
        except Exception as e:
            logger.error(f"Error removing duplicates: {str(e)}")
            return 0
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the job database.
        
        Returns:
            Dictionary with database statistics.
        """
        try:
            # Count all listings
            raw_count = self.repository.raw_collection.count_documents({})
            processed_count = self.processed_collection.count_documents({})
            
            # Count active listings
            active_count = self.processed_collection.count_documents({
                "$or": [{"expired": {"$exists": False}}, {"expired": False}],
                "$or": [{"is_duplicate": {"$exists": False}}, {"is_duplicate": False}]
            })
            
            # Count expired listings
            expired_count = self.processed_collection.count_documents({"expired": True})
            
            # Count duplicate listings
            duplicate_count = self.processed_collection.count_documents({"is_duplicate": True})
            
            # Count clusters
            cluster_count = self.cluster_manager.cluster_collection.count_documents({})
            
            # Get newest listing date
            newest_listing = self.processed_collection.find_one(
                {},
                sort=[("created_at", -1)]
            )
            newest_date = newest_listing.get("created_at") if newest_listing else None
            
            # Get oldest listing date
            oldest_listing = self.processed_collection.find_one(
                {},
                sort=[("created_at", 1)]
            )
            oldest_date = oldest_listing.get("created_at") if oldest_listing else None
            
            # Return stats
            return {
                "raw_listings": raw_count,
                "processed_listings": processed_count,
                "active_listings": active_count,
                "expired_listings": expired_count,
                "duplicate_listings": duplicate_count,
                "clusters": cluster_count,
                "newest_listing_date": newest_date,
                "oldest_listing_date": oldest_date,
                "generated_at": datetime.utcnow()
            }
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting database stats: {str(e)}")
            return {
                "error": f"Database error: {str(e)}",
                "generated_at": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {str(e)}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow()
            }
    
    def maintain_listing_count(self) -> Tuple[int, int]:
        """
        Maintain the max listing count by removing oldest listings if needed.
        
        Returns:
            Tuple of (listings_removed, current_count).
        """
        try:
            # Get current count of active listings
            current_count = self.processed_collection.count_documents({
                "$or": [{"expired": {"$exists": False}}, {"expired": False}],
                "$or": [{"is_duplicate": {"$exists": False}}, {"is_duplicate": False}]
            })
            
            # Check if we're over the limit
            if current_count <= self.max_listings:
                logger.info(f"Listing count ({current_count}) within limit ({self.max_listings})")
                return 0, current_count
            
            # Calculate how many to expire
            to_expire = current_count - self.max_listings
            logger.info(f"Need to expire {to_expire} listings to maintain limit of {self.max_listings}")
            
            # Find the oldest active listings
            old_listings = list(self.processed_collection.find(
                {
                    "$or": [{"expired": {"$exists": False}}, {"expired": False}],
                    "$or": [{"is_duplicate": {"$exists": False}}, {"is_duplicate": False}]
                },
                sort=[("created_at", 1)],
                limit=to_expire
            ))
            
            # Mark them as expired
            expired_count = 0
            for listing in old_listings:
                listing_id = str(listing["_id"])
                self.repository.update_processed_listing(
                    listing_id,
                    {
                        "expired": True,
                        "expired_reason": "database_size_limit",
                        "updated_at": datetime.utcnow()
                    }
                )
                expired_count += 1
            
            logger.info(f"Expired {expired_count} old listings to maintain database size")
            return expired_count, current_count - expired_count
            
        except Exception as e:
            logger.error(f"Error maintaining listing count: {str(e)}")
            return 0, 0
    
    def perform_daily_update(self) -> Dict[str, Any]:
        """
        Perform a daily update of the job database.
        
        This includes collecting new listings, processing them,
        updating clusters, and managing the database size.
        
        Returns:
            Dictionary with update statistics.
        """
        try:
            logger.info("Starting daily database update")
            
            # Mark expired listings
            expired_count = self.mark_expired_listings()
            
            # Remove duplicates
            duplicate_count = self.remove_duplicates()
            
            # Collect new listings (limited to maintain database size)
            logger.info("Collecting new job listings")
            company_results, field_results = self.collector.collect_all()
            
            # Count collected listings
            collected_count = sum(len(ids) for ids in company_results.values())
            collected_count += sum(len(ids) for ids in field_results.values())
            
            # Process new listings
            logger.info("Processing new job listings")
            processed_count, total_count = self.processor.process_all()
            
            # Cluster jobs if we processed new ones
            if processed_count > 0:
                logger.info("Updating job clusters")
                cluster_ids = self.cluster_manager.create_clusters()
                cluster_count = len(cluster_ids)
                
                # Update cluster summaries
                summary_count = self.cluster_manager.update_cluster_summaries()
            else:
                cluster_count = 0
                summary_count = 0
            
            # Maintain database size
            removed_count, current_count = self.maintain_listing_count()
            
            # Get database stats
            stats = self.get_database_stats()
            
            # Create update report
            report = {
                "update_time": datetime.utcnow(),
                "expired_count": expired_count,
                "duplicate_count": duplicate_count,
                "collected_count": collected_count,
                "processed_count": processed_count,
                "cluster_count": cluster_count,
                "summary_count": summary_count,
                "removed_count": removed_count,
                "current_active_listings": current_count,
                "database_stats": stats
            }
            
            # Store update report in database
            update_collection = mongodb.get_collection("update_reports")
            update_collection.insert_one(report)
            
            logger.info(f"Daily update complete: {processed_count} new listings processed")
            return report
            
        except Exception as e:
            logger.error(f"Error during daily update: {str(e)}")
            return {"error": str(e)}


# Global instance
update_manager = UpdateManager() 