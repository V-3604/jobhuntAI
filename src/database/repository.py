"""
Repository for job listings data operations in MongoDB.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from bson.objectid import ObjectId
from loguru import logger
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.results import DeleteResult, InsertOneResult, UpdateResult

from src.database.mongodb import mongodb


class JobRepository:
    """
    Repository for job listings data operations in MongoDB.
    
    This class handles all CRUD operations for job listings.
    """
    
    def __init__(self):
        """Initialize the repository."""
        self.raw_collection = mongodb.get_collection("raw_listings")
        self.processed_collection = mongodb.get_collection("processed_listings")
        self.embeddings_collection = mongodb.get_collection("embeddings")
        self.companies_collection = mongodb.get_collection("companies")
    
    def insert_raw_listing(self, listing: Dict[str, Any]) -> str:
        """
        Insert a raw job listing into the database.
        
        Args:
            listing: Raw job listing data.
            
        Returns:
            ID of the inserted document.
            
        Raises:
            PyMongoError: If insertion fails.
        """
        if "collected_at" not in listing:
            listing["collected_at"] = datetime.utcnow()
        
        try:
            result: InsertOneResult = self.raw_collection.insert_one(listing)
            logger.debug(f"Inserted raw listing with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Duplicate listing found: {listing.get('url', 'N/A')}")
            raise
        except PyMongoError as e:
            logger.error(f"Failed to insert raw listing: {str(e)}")
            raise
    
    def insert_processed_listing(self, listing: Dict[str, Any]) -> str:
        """
        Insert a processed job listing into the database.
        
        Args:
            listing: Processed job listing data.
            
        Returns:
            ID of the inserted document.
            
        Raises:
            PyMongoError: If insertion fails.
        """
        # Add timestamps
        if "created_at" not in listing:
            listing["created_at"] = datetime.utcnow()
        if "updated_at" not in listing:
            listing["updated_at"] = listing["created_at"]
        
        try:
            # Check if a listing with the same URL already exists
            if "url" in listing:
                existing = self.processed_collection.find_one({"url": listing["url"]})
                if existing:
                    # Update existing listing instead of inserting
                    listing["updated_at"] = datetime.utcnow()
                    self.update_processed_listing(str(existing["_id"]), listing)
                    return str(existing["_id"])
            
            result: InsertOneResult = self.processed_collection.insert_one(listing)
            logger.debug(f"Inserted processed listing with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Duplicate processed listing found: {listing.get('url', 'N/A')}")
            raise
        except PyMongoError as e:
            logger.error(f"Failed to insert processed listing: {str(e)}")
            raise
    
    def insert_embedding(self, embedding_data: Dict[str, Any]) -> str:
        """
        Insert an embedding for a job listing.
        
        Args:
            embedding_data: Embedding data including vector and metadata.
            
        Returns:
            ID of the inserted document.
            
        Raises:
            PyMongoError: If insertion fails.
        """
        try:
            result: InsertOneResult = self.embeddings_collection.insert_one(embedding_data)
            logger.debug(f"Inserted embedding with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to insert embedding: {str(e)}")
            raise
    
    def get_raw_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a raw job listing by ID.
        
        Args:
            listing_id: ID of the listing.
            
        Returns:
            Raw job listing document or None if not found.
        """
        try:
            result = self.raw_collection.find_one({"_id": ObjectId(listing_id)})
            return result
        except PyMongoError as e:
            logger.error(f"Error retrieving raw listing {listing_id}: {str(e)}")
            return None
    
    def get_processed_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a processed job listing by ID.
        
        Args:
            listing_id: ID of the listing.
            
        Returns:
            Processed job listing document or None if not found.
        """
        try:
            result = self.processed_collection.find_one({"_id": ObjectId(listing_id)})
            return result
        except PyMongoError as e:
            logger.error(f"Error retrieving processed listing {listing_id}: {str(e)}")
            return None
    
    def get_processed_listing_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get a processed job listing by URL.
        
        Args:
            url: URL of the job listing.
            
        Returns:
            Processed job listing document or None if not found.
        """
        try:
            result = self.processed_collection.find_one({"url": url})
            return result
        except PyMongoError as e:
            logger.error(f"Error retrieving processed listing by URL {url}: {str(e)}")
            return None
    
    def update_processed_listing(self, listing_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a processed job listing.
        
        Args:
            listing_id: ID of the listing to update.
            update_data: New data for the listing.
            
        Returns:
            True if update was successful, False otherwise.
        """
        try:
            # Ensure updated_at is set
            if "updated_at" not in update_data:
                update_data["updated_at"] = datetime.utcnow()
            
            result: UpdateResult = self.processed_collection.update_one(
                {"_id": ObjectId(listing_id)},
                {"$set": update_data}
            )
            
            success = result.modified_count > 0
            if success:
                logger.debug(f"Updated processed listing {listing_id}")
            else:
                logger.warning(f"No update performed for listing {listing_id}")
            
            return success
        except PyMongoError as e:
            logger.error(f"Failed to update processed listing {listing_id}: {str(e)}")
            return False
    
    def get_unprocessed_raw_listings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get raw listings that haven't been processed yet.
        
        Args:
            limit: Maximum number of listings to return.
            
        Returns:
            List of unprocessed raw job listings.
        """
        try:
            # Find raw listings that don't have a corresponding processed listing
            pipeline = [
                {"$lookup": {
                    "from": "processed_listings",
                    "localField": "url",
                    "foreignField": "url",
                    "as": "processed"
                }},
                {"$match": {"processed": {"$size": 0}}},
                {"$limit": limit}
            ]
            
            results = list(self.raw_collection.aggregate(pipeline))
            logger.debug(f"Found {len(results)} unprocessed raw listings")
            return results
        except PyMongoError as e:
            logger.error(f"Error retrieving unprocessed raw listings: {str(e)}")
            return []
    
    def delete_raw_listing(self, listing_id: str) -> bool:
        """
        Delete a raw job listing.
        
        Args:
            listing_id: ID of the listing to delete.
            
        Returns:
            True if deletion was successful, False otherwise.
        """
        try:
            result: DeleteResult = self.raw_collection.delete_one({"_id": ObjectId(listing_id)})
            success = result.deleted_count > 0
            
            if success:
                logger.debug(f"Deleted raw listing {listing_id}")
            else:
                logger.warning(f"No raw listing found for deletion with ID {listing_id}")
            
            return success
        except PyMongoError as e:
            logger.error(f"Failed to delete raw listing {listing_id}: {str(e)}")
            return False
    
    def delete_processed_listing(self, listing_id: str) -> bool:
        """
        Delete a processed job listing.
        
        Args:
            listing_id: ID of the listing to delete.
            
        Returns:
            True if deletion was successful, False otherwise.
        """
        try:
            result: DeleteResult = self.processed_collection.delete_one({"_id": ObjectId(listing_id)})
            success = result.deleted_count > 0
            
            if success:
                logger.debug(f"Deleted processed listing {listing_id}")
            else:
                logger.warning(f"No processed listing found for deletion with ID {listing_id}")
            
            return success
        except PyMongoError as e:
            logger.error(f"Failed to delete processed listing {listing_id}: {str(e)}")
            return False
    
    def get_listings_by_company(self, company: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get job listings for a specific company.
        
        Args:
            company: Company name.
            limit: Maximum number of listings to return.
            
        Returns:
            List of job listings for the company.
        """
        try:
            # Case-insensitive search for company name
            results = list(self.processed_collection.find(
                {"company": {"$regex": company, "$options": "i"}}
            ).limit(limit))
            
            logger.debug(f"Found {len(results)} listings for company {company}")
            return results
        except PyMongoError as e:
            logger.error(f"Error retrieving listings for company {company}: {str(e)}")
            return []
    
    def get_listings_by_field(self, field: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get job listings for a specific engineering field.
        
        Args:
            field: Engineering field.
            limit: Maximum number of listings to return.
            
        Returns:
            List of job listings for the engineering field.
        """
        try:
            # Case-insensitive search for engineering field
            results = list(self.processed_collection.find(
                {"engineering_field": {"$regex": field, "$options": "i"}}
            ).limit(limit))
            
            logger.debug(f"Found {len(results)} listings for field {field}")
            return results
        except PyMongoError as e:
            logger.error(f"Error retrieving listings for field {field}: {str(e)}")
            return []
    
    def get_listings_with_skill(self, skill: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get job listings requiring a specific skill.
        
        Args:
            skill: Required skill.
            limit: Maximum number of listings to return.
            
        Returns:
            List of job listings requiring the skill.
        """
        try:
            # Case-insensitive search for skill in required_skills array
            results = list(self.processed_collection.find(
                {"required_skills": {"$regex": skill, "$options": "i"}}
            ).limit(limit))
            
            logger.debug(f"Found {len(results)} listings requiring skill {skill}")
            return results
        except PyMongoError as e:
            logger.error(f"Error retrieving listings with skill {skill}: {str(e)}")
            return []
    
    def count_listings_by_field(self) -> Dict[str, int]:
        """
        Count job listings by engineering field.
        
        Returns:
            Dictionary mapping engineering fields to counts.
        """
        try:
            pipeline = [
                {"$group": {"_id": "$engineering_field", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            results = self.processed_collection.aggregate(pipeline)
            counts = {doc["_id"]: doc["count"] for doc in results if doc["_id"]}
            
            logger.debug(f"Counted listings by field: {counts}")
            return counts
        except PyMongoError as e:
            logger.error(f"Error counting listings by field: {str(e)}")
            return {}


# Global job repository instance
job_repository = JobRepository() 