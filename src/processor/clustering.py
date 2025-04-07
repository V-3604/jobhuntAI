"""
Clustering system for job listings.

This module handles the clustering of job listings into categories based on
job attributes like field, required skills, company, and other metadata.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from loguru import logger
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from src.database.mongodb import mongodb
from src.database.repository import job_repository
from src.processor.openai_client import openai_client
from src.utils.config import config


class ClusterManager:
    """
    Manager for job listing clusters.
    
    Handles creation, update, and retrieval of job clusters.
    """
    
    def __init__(self):
        """Initialize the cluster manager."""
        self.repository = job_repository
        self.openai = openai_client
        
        # Get MongoDB collections
        self.cluster_collection = mongodb.get_collection("clusters")
        self.cluster_summary_collection = mongodb.get_collection("cluster_summaries")
        
        # Cluster configuration
        self.config = config.get("clustering", {})
        self.num_clusters = self.config.get("num_clusters", 10)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.7)
        
        logger.info(f"Cluster manager initialized with {self.num_clusters} target clusters")
    
    def create_clusters(self) -> List[str]:
        """
        Create clusters from all processed job listings.
        
        Returns:
            List of cluster IDs created.
        """
        logger.info("Creating job listing clusters")
        
        try:
            # Get all listings with embeddings
            listings_with_embeddings = self._get_listings_with_embeddings()
            if not listings_with_embeddings:
                logger.warning("No listings with embeddings found for clustering")
                return []
            
            # Create embedding matrix and track listing IDs
            embedding_matrix = []
            listing_ids = []
            
            for listing_id, embedding in listings_with_embeddings:
                embedding_matrix.append(embedding)
                listing_ids.append(listing_id)
            
            # Convert to numpy array
            embedding_matrix = np.array(embedding_matrix)
            
            # Use DBSCAN for clustering
            clustering = DBSCAN(
                eps=1.0 - self.similarity_threshold,  # Convert similarity to distance
                min_samples=2,
                metric='cosine'
            ).fit(embedding_matrix)
            
            # Get cluster labels
            labels = clustering.labels_
            
            # Create clusters dictionary {cluster_id: [listing_ids]}
            clusters = {}
            for i, label in enumerate(labels):
                # -1 means noise (no cluster)
                if label == -1:
                    continue
                
                if label not in clusters:
                    clusters[label] = []
                
                clusters[label].append(listing_ids[i])
            
            # Store clusters in database
            cluster_ids = []
            for label, cluster_listing_ids in clusters.items():
                cluster_id = self._store_cluster(label, cluster_listing_ids)
                if cluster_id:
                    cluster_ids.append(cluster_id)
                    # Generate and store cluster summary
                    self._generate_cluster_summary(cluster_id)
            
            logger.info(f"Created {len(cluster_ids)} clusters from {len(listing_ids)} listings")
            return cluster_ids
            
        except Exception as e:
            logger.error(f"Error creating clusters: {str(e)}")
            return []
    
    def _get_listings_with_embeddings(self) -> List[Tuple[str, List[float]]]:
        """
        Get all processed job listings with their embeddings.
        
        Returns:
            List of tuples (listing_id, embedding).
        """
        try:
            # Get all embeddings with listing IDs
            embeddings = list(self.repository.embeddings_collection.find(
                {"listing_id": {"$exists": True, "$ne": None}}
            ))
            
            result = []
            for embedding_doc in embeddings:
                listing_id = embedding_doc.get("listing_id")
                vector = embedding_doc.get("vector")
                
                if not listing_id or not vector:
                    continue
                
                result.append((str(listing_id), vector))
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting listings with embeddings: {str(e)}")
            return []
    
    def _store_cluster(self, label: int, listing_ids: List[str]) -> Optional[str]:
        """
        Store a cluster in the database.
        
        Args:
            label: Cluster label.
            listing_ids: List of listing IDs in the cluster.
            
        Returns:
            Cluster ID if successful, None otherwise.
        """
        try:
            # Get metadata from first few listings to identify the cluster
            metadata = self._extract_cluster_metadata(listing_ids[:5])
            
            # Create cluster document
            cluster = {
                "label": int(label),
                "name": metadata.get("name", f"Cluster {label}"),
                "size": len(listing_ids),
                "listing_ids": listing_ids,
                "metadata": metadata,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            
            # Insert cluster
            result = self.cluster_collection.insert_one(cluster)
            logger.debug(f"Stored cluster {label} with ID {result.inserted_id}")
            
            # Update listings with cluster ID
            for listing_id in listing_ids:
                self.repository.update_processed_listing(
                    listing_id,
                    {"cluster_id": str(result.inserted_id)}
                )
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error storing cluster {label}: {str(e)}")
            return None
    
    def _extract_cluster_metadata(self, listing_ids: List[str]) -> Dict[str, Any]:
        """
        Extract metadata to identify a cluster based on sample listings.
        
        Args:
            listing_ids: List of listing IDs to sample from.
            
        Returns:
            Dictionary of metadata about the cluster.
        """
        listings = []
        for listing_id in listing_ids:
            listing = self.repository.get_processed_listing(listing_id)
            if listing:
                listings.append(listing)
        
        if not listings:
            return {"name": "Unknown Cluster"}
        
        # Extract common fields
        fields = [listing.get("engineering_field", "") for listing in listings]
        common_field = max(set(fields), key=fields.count) if fields else ""
        
        # Extract common companies
        companies = [listing.get("company", "") for listing in listings]
        common_companies = set(filter(None, companies))
        
        # Extract common skills
        all_skills: Set[str] = set()
        for listing in listings:
            skills = listing.get("required_skills", [])
            if skills:
                all_skills.update(skills)
        
        # Create cluster name
        if common_field:
            name = f"{common_field} Jobs"
        elif common_companies and len(common_companies) <= 3:
            name = f"{', '.join(list(common_companies)[:3])} Jobs"
        elif all_skills:
            top_skills = list(all_skills)[:3]
            name = f"Jobs requiring {', '.join(top_skills)}"
        else:
            name = f"Job Cluster (ID: {listing_ids[0][:6]})"
        
        return {
            "name": name,
            "common_field": common_field,
            "common_companies": list(common_companies)[:5],
            "common_skills": list(all_skills)[:10],
        }
    
    def _generate_cluster_summary(self, cluster_id: str) -> Optional[str]:
        """
        Generate a summary for a cluster.
        
        Args:
            cluster_id: ID of the cluster.
            
        Returns:
            ID of the summary document if successful, None otherwise.
        """
        try:
            # Get the cluster
            cluster = self.cluster_collection.find_one({"_id": mongodb.db["clusters"]._id_to_type(cluster_id)})
            if not cluster:
                logger.warning(f"Cluster {cluster_id} not found")
                return None
            
            # Get a sample of listings
            listing_ids = cluster.get("listing_ids", [])
            sample_size = min(5, len(listing_ids))
            sample_ids = listing_ids[:sample_size]
            
            sample_listings = []
            for listing_id in sample_ids:
                listing = self.repository.get_processed_listing(listing_id)
                if listing:
                    sample_listings.append(listing)
            
            # Create content for summary generation
            listings_text = ""
            for i, listing in enumerate(sample_listings):
                listings_text += f"\nListing {i+1}:\n"
                listings_text += f"Title: {listing.get('title', 'Unknown')}\n"
                listings_text += f"Company: {listing.get('company', 'Unknown')}\n"
                skills = listing.get('required_skills', [])
                if skills:
                    listings_text += f"Skills: {', '.join(skills)}\n"
                field = listing.get('engineering_field', '')
                if field:
                    listings_text += f"Field: {field}\n"
            
            # Generate summary using OpenAI
            prompt = (
                f"The following are {sample_size} sample job listings from a cluster of {len(listing_ids)} total listings. "
                f"Generate a concise summary (3-4 paragraphs) that describes the common themes, skills, "
                f"requirements, and opportunities in this job cluster. Focus on what makes these jobs similar "
                f"and what key skills would help someone succeed in these roles.\n\n"
                f"{listings_text}"
            )
            
            messages = [
                {"role": "system", "content": "You are a career advisor summarizing job clusters for students."},
                {"role": "user", "content": prompt}
            ]
            
            response = self.openai.generate_chat_completion(messages=messages)
            summary_text = response.choices[0].message.content
            
            # Create metadata from cluster
            metadata = cluster.get("metadata", {})
            
            # Create summary document
            summary = {
                "cluster_id": cluster_id,
                "name": metadata.get("name", f"Cluster Summary"),
                "summary": summary_text,
                "sample_size": sample_size,
                "total_listings": len(listing_ids),
                "metadata": metadata,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            
            # Insert or update summary
            existing_summary = self.cluster_summary_collection.find_one({"cluster_id": cluster_id})
            if existing_summary:
                summary["updated_at"] = datetime.utcnow()
                self.cluster_summary_collection.update_one(
                    {"_id": existing_summary["_id"]},
                    {"$set": summary}
                )
                summary_id = str(existing_summary["_id"])
            else:
                result = self.cluster_summary_collection.insert_one(summary)
                summary_id = str(result.inserted_id)
            
            logger.debug(f"Generated summary for cluster {cluster_id}")
            return summary_id
            
        except Exception as e:
            logger.error(f"Error generating cluster summary for {cluster_id}: {str(e)}")
            return None
    
    def update_cluster_summaries(self) -> int:
        """
        Update summaries for all clusters.
        
        Returns:
            Number of summaries updated.
        """
        try:
            # Get all clusters
            clusters = list(self.cluster_collection.find({}))
            
            updated_count = 0
            for cluster in clusters:
                cluster_id = str(cluster["_id"])
                summary_id = self._generate_cluster_summary(cluster_id)
                if summary_id:
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} cluster summaries")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating cluster summaries: {str(e)}")
            return 0
    
    def get_cluster_summary(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the summary for a cluster.
        
        Args:
            cluster_id: ID of the cluster.
            
        Returns:
            Cluster summary document or None if not found.
        """
        try:
            summary = self.cluster_summary_collection.find_one({"cluster_id": cluster_id})
            return summary
            
        except Exception as e:
            logger.error(f"Error getting cluster summary for {cluster_id}: {str(e)}")
            return None
    
    def get_cluster_for_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the cluster for a listing.
        
        Args:
            listing_id: ID of the listing.
            
        Returns:
            Cluster document or None if not found.
        """
        try:
            # Get the listing
            listing = self.repository.get_processed_listing(listing_id)
            if not listing:
                logger.warning(f"Listing {listing_id} not found")
                return None
            
            # Check if it has a cluster ID
            cluster_id = listing.get("cluster_id")
            if not cluster_id:
                logger.warning(f"Listing {listing_id} has no cluster ID")
                return None
            
            # Get the cluster
            cluster = self.cluster_collection.find_one({"_id": mongodb.db["clusters"]._id_to_type(cluster_id)})
            return cluster
            
        except Exception as e:
            logger.error(f"Error getting cluster for listing {listing_id}: {str(e)}")
            return None


# Global instance
cluster_manager = ClusterManager() 