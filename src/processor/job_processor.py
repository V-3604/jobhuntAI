"""
Job processor for transforming raw job listings into processed ones.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from src.database.repository import job_repository
from src.processor.openai_client import openai_client
from src.utils.config import config


class JobProcessor:
    """
    Processor for job listings data.
    
    Transforms raw job listings into processed ones with extracted metadata.
    """
    
    def __init__(self):
        """Initialize the job processor."""
        self.repository = job_repository
        self.openai = openai_client
        
        # Get batch size from config
        self.batch_size = config["openai"].get("batch_size", 10)
        
        logger.info(f"JobProcessor initialized with batch size {self.batch_size}")
    
    def process_raw_listing(self, raw_listing: Dict[str, Any]) -> Optional[str]:
        """
        Process a raw job listing into a processed one.
        
        Args:
            raw_listing: Raw job listing data.
            
        Returns:
            ID of the processed listing or None if processing failed.
        """
        try:
            # Extract URL
            url = raw_listing.get("url")
            if not url:
                logger.warning("Raw listing has no URL, cannot process")
                return None
            
            # Check if already processed
            existing = self.repository.get_processed_listing_by_url(url)
            if existing:
                logger.info(f"Listing already processed: {url}")
                return str(existing["_id"])
            
            # Extract content
            content = raw_listing.get("content")
            title = raw_listing.get("title", "")
            company = raw_listing.get("company", "")
            
            if not content:
                logger.warning(f"Raw listing has no content, cannot process: {url}")
                return None
            
            # Extract metadata using OpenAI
            metadata = self.openai.extract_job_metadata(content)
            
            # Fill in missing fields from raw listing
            if not metadata.get("title") and title:
                metadata["title"] = title
            if not metadata.get("company") and company:
                metadata["company"] = company
            
            # Add URL and source
            metadata["url"] = url
            metadata["source"] = raw_listing.get("source", "unknown")
            
            # Add timestamps
            metadata["created_at"] = datetime.utcnow()
            metadata["updated_at"] = metadata["created_at"]
            metadata["collected_at"] = raw_listing.get("collected_at", metadata["created_at"])
            
            # Store raw listing ID for reference
            metadata["raw_listing_id"] = str(raw_listing["_id"])
            
            # If engineering field is missing, classify it
            if not metadata.get("engineering_field"):
                metadata["engineering_field"] = self.openai.classify_job_field(content)
            
            # If required skills are missing, extract them
            if not metadata.get("required_skills"):
                metadata["required_skills"] = self.openai.extract_skills(content)
            
            # Generate embedding
            embedding = self.generate_listing_embedding(content)
            if embedding:
                # Store embedding in dedicated collection
                embedding_data = {
                    "listing_id": None,  # Will be updated after processed listing is inserted
                    "url": url,
                    "vector": embedding,
                    "created_at": metadata["created_at"]
                }
                
                embedding_id = self.repository.insert_embedding(embedding_data)
                metadata["embedding_id"] = embedding_id
            
            # Insert processed listing
            processed_id = self.repository.insert_processed_listing(metadata)
            
            # Update embedding with processed listing ID if it was created
            if embedding and processed_id:
                self.repository.embeddings_collection.update_one(
                    {"_id": embedding_id},
                    {"$set": {"listing_id": processed_id}}
                )
            
            logger.info(f"Successfully processed job listing: {url}")
            return processed_id
            
        except Exception as e:
            logger.error(f"Error processing raw listing: {str(e)}")
            return None
    
    def generate_listing_embedding(self, content: str) -> Optional[List[float]]:
        """
        Generate an embedding vector for a job listing.
        
        Args:
            content: Job listing content text.
            
        Returns:
            Embedding vector or None if generation failed.
        """
        try:
            # Truncate content if it's very long
            max_chars = 8000  # Reasonable limit for embedding models
            if len(content) > max_chars:
                content = content[:max_chars]
            
            # Generate embedding
            embeddings = self.openai.generate_embeddings([content])
            if not embeddings:
                logger.warning("Failed to generate embedding: empty response")
                return None
            
            return embeddings[0]
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
    
    def check_for_duplicates(self, listing_id: str, threshold: float = 0.9) -> List[str]:
        """
        Check for potential duplicate listings.
        
        Args:
            listing_id: ID of the listing to check.
            threshold: Similarity threshold (0-1) for considering listings as duplicates.
            
        Returns:
            List of IDs of potential duplicate listings.
        """
        try:
            # Get the listing
            listing = self.repository.get_processed_listing(listing_id)
            if not listing:
                logger.warning(f"Listing {listing_id} not found for duplicate checking")
                return []
            
            # Check if it has an embedding
            embedding_id = listing.get("embedding_id")
            if not embedding_id:
                logger.warning(f"Listing {listing_id} has no embedding, using content comparison")
                
                # Fallback to content comparison for a few recent listings (expensive)
                recent_listings = list(self.repository.processed_collection.find(
                    {"_id": {"$ne": listing_id}},
                    sort=[("created_at", -1)],
                    limit=5
                ))
                
                duplicates = []
                for recent in recent_listings:
                    # Get content for both listings
                    original_raw = self.repository.get_raw_listing(listing.get("raw_listing_id", ""))
                    compare_raw = self.repository.get_raw_listing(recent.get("raw_listing_id", ""))
                    
                    if original_raw and compare_raw:
                        similarity = self.openai.compare_listings_for_similarity(
                            original_raw.get("content", ""),
                            compare_raw.get("content", "")
                        )
                        
                        if similarity >= threshold:
                            duplicates.append(str(recent["_id"]))
                
                return duplicates
            
            # Get the embedding
            embedding_doc = self.repository.embeddings_collection.find_one({"_id": embedding_id})
            if not embedding_doc or "vector" not in embedding_doc:
                logger.warning(f"Embedding {embedding_id} not found or invalid")
                return []
            
            # Get the vector
            vector = embedding_doc["vector"]
            
            # Find similar embeddings
            # Note: This is a simplified approach; in production, you'd use a vector database
            # or specialized index for efficient similarity search
            
            # Get all embeddings
            all_embeddings = list(self.repository.embeddings_collection.find(
                {"_id": {"$ne": embedding_id}, "listing_id": {"$exists": True, "$ne": None}}
            ))
            
            # Calculate similarity for each
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            duplicates = []
            
            for emb_doc in all_embeddings:
                compare_vector = emb_doc.get("vector")
                compare_listing_id = emb_doc.get("listing_id")
                
                if not compare_vector or not compare_listing_id:
                    continue
                
                # Calculate cosine similarity
                similarity = cosine_similarity(
                    [vector],
                    [compare_vector]
                )[0][0]
                
                if similarity >= threshold:
                    duplicates.append(str(compare_listing_id))
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {str(e)}")
            return []
    
    def process_batch(self, batch_size: Optional[int] = None) -> Tuple[int, int]:
        """
        Process a batch of raw listings.
        
        Args:
            batch_size: Number of listings to process. Defaults to self.batch_size.
            
        Returns:
            Tuple of (number of listings processed, number of successful processes).
        """
        batch_size = batch_size or self.batch_size
        
        # Get unprocessed listings
        unprocessed = self.repository.get_unprocessed_raw_listings(limit=batch_size)
        
        if not unprocessed:
            logger.info("No unprocessed listings found")
            return 0, 0
        
        logger.info(f"Processing batch of {len(unprocessed)} listings")
        
        processed_count = 0
        success_count = 0
        
        for raw_listing in unprocessed:
            try:
                processed_id = self.process_raw_listing(raw_listing)
                processed_count += 1
                
                if processed_id:
                    success_count += 1
                    
                    # Check for duplicates
                    duplicates = self.check_for_duplicates(processed_id)
                    if duplicates:
                        logger.info(f"Found {len(duplicates)} potential duplicates for listing {processed_id}")
                        
                        # Mark as duplicate
                        self.repository.update_processed_listing(
                            processed_id,
                            {"potential_duplicates": duplicates}
                        )
                
            except Exception as e:
                logger.error(f"Error processing listing {raw_listing.get('_id')}: {str(e)}")
        
        logger.info(f"Batch processing complete: {success_count}/{processed_count} successful")
        return processed_count, success_count
    
    def process_all(self, max_listings: Optional[int] = None) -> Tuple[int, int]:
        """
        Process all unprocessed raw listings.
        
        Args:
            max_listings: Maximum number of listings to process. If None, process all.
            
        Returns:
            Tuple of (number of listings processed, number of successful processes).
        """
        total_processed = 0
        total_success = 0
        
        while True:
            # Check if we've hit the maximum
            if max_listings is not None and total_processed >= max_listings:
                logger.info(f"Reached maximum of {max_listings} listings, stopping")
                break
            
            # Calculate remaining
            remaining = None
            if max_listings is not None:
                remaining = max_listings - total_processed
                if remaining <= 0:
                    break
                
                # Process a batch with adjusted size if needed
                batch_size = min(self.batch_size, remaining)
                processed, success = self.process_batch(batch_size=batch_size)
            else:
                # Process a standard batch
                processed, success = self.process_batch()
            
            # Update totals
            total_processed += processed
            total_success += success
            
            # If nothing was processed, we're done
            if processed == 0:
                break
        
        logger.info(f"All processing complete: {total_success}/{total_processed} successful")
        return total_processed, total_success


# Global job processor instance
job_processor = JobProcessor() 