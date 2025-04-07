"""
Job collector for collecting job listings from search results.
"""
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from src.collector.content_scraper import content_scraper
from src.collector.google_search import google_search_client
from src.database.repository import job_repository
from src.utils.config import config


class JobCollector:
    """
    Collector for job listings.
    
    Manages the collection of job listings from search results.
    """
    
    def __init__(self):
        """Initialize the job collector."""
        self.google_client = google_search_client
        self.scraper = content_scraper
        self.repository = job_repository
        
        # Get configuration
        self.collection_config = config["collection"]
        self.companies = self.collection_config.get("companies", [])
        self.engineering_fields = self.collection_config.get("engineering_fields", [])
        self.keywords = self.collection_config.get("keywords", [])
        self.max_results_per_query = self.collection_config.get("max_results_per_query", 10)
        
        logger.info(f"Job collector initialized with {len(self.companies)} companies and {len(self.keywords)} keywords")
    
    def collect_company_jobs(self, company: str) -> List[str]:
        """
        Collect job listings for a specific company.
        
        Args:
            company: Company name.
            
        Returns:
            List of IDs of collected job listings.
        """
        logger.info(f"Collecting jobs for company: {company}")
        
        try:
            # Search for jobs
            search_results = self.google_client.search_company_jobs(
                company=company,
                keywords=self.keywords,
                max_results=self.max_results_per_query,
            )
            
            if not search_results:
                logger.warning(f"No search results found for company: {company}")
                return []
            
            logger.info(f"Found {len(search_results)} search results for company: {company}")
            
            # Scrape job content
            job_listings = self.scraper.scrape_search_results(search_results)
            
            if not job_listings:
                logger.warning(f"No job listings scraped for company: {company}")
                return []
            
            logger.info(f"Scraped {len(job_listings)} job listings for company: {company}")
            
            # Store job listings
            listing_ids = []
            for listing in job_listings:
                try:
                    # Add company to listing if not present
                    if not listing.get("company"):
                        listing["company"] = company
                    
                    # Store in repository
                    listing_id = self.repository.insert_raw_listing(listing)
                    listing_ids.append(listing_id)
                    
                except Exception as e:
                    logger.error(f"Error storing job listing for company {company}: {str(e)}")
            
            logger.info(f"Stored {len(listing_ids)} job listings for company: {company}")
            return listing_ids
            
        except Exception as e:
            logger.error(f"Error collecting jobs for company {company}: {str(e)}")
            return []
    
    def collect_field_jobs(self, field: str) -> List[str]:
        """
        Collect job listings for a specific engineering field.
        
        Args:
            field: Engineering field.
            
        Returns:
            List of IDs of collected job listings.
        """
        logger.info(f"Collecting jobs for field: {field}")
        
        try:
            # Create field-specific keywords
            field_keywords = self.keywords.copy()
            field_keywords.append(field.lower())
            
            # Create the query string
            keywords_joined = " OR ".join([f'"{kw}"' for kw in self.keywords])
            query = f'"{field}" jobs ({keywords_joined})'
            
            # Search for jobs
            search_results = self.google_client.search_all_pages(
                query=query,
                max_results=self.max_results_per_query,
            )
            
            if not search_results:
                logger.warning(f"No search results found for field: {field}")
                return []
            
            logger.info(f"Found {len(search_results)} search results for field: {field}")
            
            # Scrape job content
            job_listings = self.scraper.scrape_search_results(search_results)
            
            if not job_listings:
                logger.warning(f"No job listings scraped for field: {field}")
                return []
            
            logger.info(f"Scraped {len(job_listings)} job listings for field: {field}")
            
            # Store job listings
            listing_ids = []
            for listing in job_listings:
                try:
                    # Add field to listing metadata
                    if "search_metadata" not in listing:
                        listing["search_metadata"] = {}
                    
                    listing["search_metadata"]["engineering_field"] = field
                    
                    # Store in repository
                    listing_id = self.repository.insert_raw_listing(listing)
                    listing_ids.append(listing_id)
                    
                except Exception as e:
                    logger.error(f"Error storing job listing for field {field}: {str(e)}")
            
            logger.info(f"Stored {len(listing_ids)} job listings for field: {field}")
            return listing_ids
            
        except Exception as e:
            logger.error(f"Error collecting jobs for field {field}: {str(e)}")
            return []
    
    def collect_all_companies(self) -> Dict[str, List[str]]:
        """
        Collect job listings for all configured companies.
        
        Returns:
            Dictionary mapping company names to lists of listing IDs.
        """
        results = {}
        
        for company in self.companies:
            try:
                listing_ids = self.collect_company_jobs(company)
                results[company] = listing_ids
                
            except Exception as e:
                logger.error(f"Error in collection for company {company}: {str(e)}")
                results[company] = []
        
        return results
    
    def collect_all_fields(self) -> Dict[str, List[str]]:
        """
        Collect job listings for all configured engineering fields.
        
        Returns:
            Dictionary mapping field names to lists of listing IDs.
        """
        results = {}
        
        for field in self.engineering_fields:
            try:
                listing_ids = self.collect_field_jobs(field)
                results[field] = listing_ids
                
            except Exception as e:
                logger.error(f"Error in collection for field {field}: {str(e)}")
                results[field] = []
        
        return results
    
    def collect_all(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Collect job listings for all companies and engineering fields.
        
        Returns:
            Tuple of (company results, field results).
        """
        logger.info("Starting full collection of job listings")
        
        # Collect company jobs
        company_results = self.collect_all_companies()
        total_company_listings = sum(len(ids) for ids in company_results.values())
        
        # Collect field jobs
        field_results = self.collect_all_fields()
        total_field_listings = sum(len(ids) for ids in field_results.values())
        
        logger.info(
            f"Collection complete: {total_company_listings} company listings, "
            f"{total_field_listings} field listings"
        )
        
        return company_results, field_results


# Global job collector instance
job_collector = JobCollector() 