"""
MongoDB connection and utility functions.
"""
from typing import Any, Dict, List, Optional, Union

import pymongo
from loguru import logger
from pymongo import MongoClient, IndexModel
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError

from src.utils.config import config


class MongoDBManager:
    """
    MongoDB database manager for handling connections and operations.
    """
    
    def __init__(self):
        """Initialize the MongoDB manager."""
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._connected = False
        
        # Get configuration
        self.db_config = config["database"]
        self.connection_string = self.db_config["connection_string"]
        self.db_name = self.db_config["database_name"]
        
        # Collection names
        self.collections = self.db_config["collections"]
    
    @property
    def client(self) -> MongoClient:
        """Get MongoDB client, connecting if necessary."""
        if self._client is None or not self._connected:
            self.connect()
        return self._client
    
    @property
    def db(self) -> Database:
        """Get MongoDB database, connecting if necessary."""
        if self._db is None or not self._connected:
            self.connect()
        return self._db
    
    def connect(self) -> None:
        """
        Connect to MongoDB database.
        
        Raises:
            ConnectionFailure: If connection to MongoDB fails.
        """
        try:
            logger.info(f"Connecting to MongoDB at {self.connection_string}")
            self._client = MongoClient(self.connection_string)
            
            # Test connection
            self._client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            self._db = self._client[self.db_name]
            self._connected = True
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {str(e)}")
            self._connected = False
            self._db = None
            raise
    
    def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client and self._connected:
            self._client.close()
            self._connected = False
            logger.info("Disconnected from MongoDB")
    
    def get_collection(self, collection_name: str) -> Collection:
        """
        Get MongoDB collection by name.
        
        Args:
            collection_name: Name of the collection.
            
        Returns:
            MongoDB collection object.
        """
        if collection_name in self.collections:
            collection_name = self.collections[collection_name]
        
        return self.db[collection_name]
    
    def setup_indexes(self) -> None:
        """
        Set up indexes defined in configuration.
        
        This ensures all necessary indexes are created for optimal query performance.
        """
        if "indexes" not in self.db_config:
            logger.warning("No indexes defined in configuration")
            return
        
        for index_config in self.db_config["indexes"]:
            collection_name = index_config["collection"]
            fields = index_config["fields"]
            options = index_config.get("options", {})
            
            collection = self.get_collection(collection_name)
            
            # Create index
            if isinstance(fields, list):
                # Multiple fields
                if len(fields) > 1:
                    # Create a compound index
                    index_spec = [(field, pymongo.ASCENDING) for field in fields]
                    index_name = "_".join(fields)
                else:
                    # Single field in a list
                    index_spec = [(fields[0], pymongo.ASCENDING)]
                    index_name = fields[0]
            else:
                # Single field as string
                index_spec = [(fields, pymongo.ASCENDING)]
                index_name = fields
            
            try:
                collection.create_index(index_spec, name=index_name, **options)
                logger.info(f"Created index {index_name} on collection {collection_name}")
            except PyMongoError as e:
                logger.error(f"Failed to create index {index_name} on collection {collection_name}: {str(e)}")
    
    def setup_ttl_index(self) -> None:
        """
        Set up TTL (Time-To-Live) index for job listings to automatically expire old entries.
        """
        ttl_days = self.db_config.get("job_ttl_days", 30)
        collection = self.get_collection("processed_listings")
        
        try:
            collection.create_index(
                [("created_at", pymongo.ASCENDING)],
                name="ttl_index",
                expireAfterSeconds=ttl_days * 24 * 60 * 60  # Convert days to seconds
            )
            logger.info(f"Created TTL index on processed_listings, expiring after {ttl_days} days")
        except PyMongoError as e:
            logger.error(f"Failed to create TTL index: {str(e)}")
    
    def initialize_collections(self) -> None:
        """
        Initialize all collections defined in configuration.
        
        This ensures all required collections exist.
        """
        for collection_name in self.collections.values():
            if collection_name not in self.db.list_collection_names():
                self.db.create_collection(collection_name)
                logger.info(f"Created collection {collection_name}")
            else:
                logger.debug(f"Collection {collection_name} already exists")
    
    def setup_database(self) -> None:
        """
        Set up the entire database - connect, initialize collections and set up indexes.
        """
        self.connect()
        self.initialize_collections()
        self.setup_indexes()
        self.setup_ttl_index()
        logger.info("Database setup complete")


# Global MongoDB manager instance
mongodb = MongoDBManager() 