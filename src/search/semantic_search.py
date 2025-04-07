"""
Semantic search functionality for job listings.
"""
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from loguru import logger
from sklearn.metrics.pairwise import cosine_similarity

from src.database.repository import job_repository
from src.processor.openai_client import openai_client
from src.utils.config import config


class SemanticSearch:
    """
    Semantic search for job listings.
    
    Uses embeddings to find semantically similar job listings.
    """
    
    def __init__(self):
        """Initialize the semantic search."""
        self.repository = job_repository
        self.openai = openai_client
        
        # Default similarity threshold
        self.similarity_threshold = 0.7
        
        logger.info("Semantic search initialized")
    
    def generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate an embedding for a search query.
        
        Args:
            query: Search query text.
            
        Returns:
            Embedding vector or None if generation failed.
        """
        try:
            embeddings = self.openai.generate_embeddings([query])
            if not embeddings:
                logger.warning("Failed to generate query embedding: empty response")
                return None
            
            return embeddings[0]
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            return None
    
    def search_by_embedding(
        self,
        query_embedding: List[float],
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for job listings using embedding similarity.
        
        Args:
            query_embedding: Query embedding vector.
            limit: Maximum number of results to return.
            threshold: Similarity threshold (0-1). Defaults to self.similarity_threshold.
            
        Returns:
            List of tuples (job listing, similarity score) sorted by similarity.
        """
        threshold = threshold or self.similarity_threshold
        
        try:
            # Get all embeddings
            embedding_docs = list(self.repository.embeddings_collection.find({
                "listing_id": {"$exists": True, "$ne": None}
            }))
            
            if not embedding_docs:
                logger.warning("No embeddings found in database")
                return []
            
            # Calculate similarity for each
            results = []
            for doc in embedding_docs:
                vector = doc.get("vector")
                listing_id = doc.get("listing_id")
                
                if not vector or not listing_id:
                    continue
                
                # Calculate cosine similarity
                similarity = cosine_similarity([query_embedding], [vector])[0][0]
                
                # Check threshold
                if similarity >= threshold:
                    # Get the actual listing
                    listing = self.repository.get_processed_listing(listing_id)
                    if listing:
                        results.append((listing, float(similarity)))
            
            # Sort by similarity (descending)
            results.sort(key=lambda x: x[1], reverse=True)
            
            # Limit results
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching by embedding: {str(e)}")
            return []
    
    def search(
        self,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for job listings using a text query.
        
        Args:
            query: Search query text.
            limit: Maximum number of results to return.
            threshold: Similarity threshold (0-1). Defaults to self.similarity_threshold.
            
        Returns:
            List of tuples (job listing, similarity score) sorted by similarity.
        """
        # Generate embedding for query
        query_embedding = self.generate_query_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []
        
        # Search by embedding
        return self.search_by_embedding(
            query_embedding=query_embedding,
            limit=limit,
            threshold=threshold,
        )
    
    def search_by_skills(
        self,
        skills: List[str],
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for job listings by required skills.
        
        Args:
            skills: List of skills to search for.
            limit: Maximum number of results to return.
            threshold: Similarity threshold (0-1). Defaults to self.similarity_threshold.
            
        Returns:
            List of tuples (job listing, similarity score) sorted by similarity.
        """
        # Create a skills query
        skills_query = "Job requiring skills in: " + ", ".join(skills)
        
        # Search using the skills query
        return self.search(
            query=skills_query,
            limit=limit,
            threshold=threshold,
        )
    
    def search_by_company_and_role(
        self,
        company: str,
        role: str,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for job listings by company and role.
        
        Args:
            company: Company name.
            role: Job role or title.
            limit: Maximum number of results to return.
            threshold: Similarity threshold (0-1). Defaults to self.similarity_threshold.
            
        Returns:
            List of tuples (job listing, similarity score) sorted by similarity.
        """
        # Create a company and role query
        query = f"{role} position at {company}"
        
        # Search using the query
        return self.search(
            query=query,
            limit=limit,
            threshold=threshold,
        )
    
    def search_by_field(
        self,
        field: str,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for job listings by engineering field.
        
        Args:
            field: Engineering field.
            limit: Maximum number of results to return.
            threshold: Similarity threshold (0-1). Defaults to self.similarity_threshold.
            
        Returns:
            List of tuples (job listing, similarity score) sorted by similarity.
        """
        # Create a field query
        query = f"Job in {field} field"
        
        # Search using the field query
        return self.search(
            query=query,
            limit=limit,
            threshold=threshold,
        )
    
    def find_similar_listings(
        self,
        listing_id: str,
        limit: int = 5,
        threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find listings similar to a given listing.
        
        Args:
            listing_id: ID of the reference listing.
            limit: Maximum number of results to return.
            threshold: Similarity threshold (0-1). Defaults to self.similarity_threshold.
            
        Returns:
            List of tuples (job listing, similarity score) sorted by similarity.
        """
        try:
            # Get the reference listing
            listing = self.repository.get_processed_listing(listing_id)
            if not listing:
                logger.warning(f"Listing {listing_id} not found")
                return []
            
            # Check if it has an embedding
            embedding_id = listing.get("embedding_id")
            if not embedding_id:
                logger.warning(f"Listing {listing_id} has no embedding")
                return []
            
            # Get the embedding
            embedding_doc = self.repository.embeddings_collection.find_one({"_id": embedding_id})
            if not embedding_doc or "vector" not in embedding_doc:
                logger.warning(f"Embedding {embedding_id} not found or invalid")
                return []
            
            # Get the vector
            vector = embedding_doc["vector"]
            
            # Search by embedding
            return self.search_by_embedding(
                query_embedding=vector,
                limit=limit + 1,  # Add 1 to account for the reference listing itself
                threshold=threshold,
            )
            
        except Exception as e:
            logger.error(f"Error finding similar listings: {str(e)}")
            return []


# Global semantic search instance
semantic_search = SemanticSearch() 