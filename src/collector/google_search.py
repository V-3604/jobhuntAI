"""
Google Programmable Search Engine client for job listings collection.
"""
import os
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.config import config
from src.utils.rate_limiter import google_cse_rate_limited, with_exponential_backoff


class GoogleSearchClient:
    """
    Client for Google Programmable Search Engine API.
    
    Handles search queries for job listings on company career pages.
    """
    
    def __init__(self):
        """Initialize the Google Search client."""
        # Get API key from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("Google API key not found. Please set GOOGLE_API_KEY environment variable.")
            raise ValueError("Google API key not found")
        
        # Get CSE ID from environment
        cse_id = os.getenv("GOOGLE_CSE_ID")
        if not cse_id:
            logger.error("Google CSE ID not found. Please set GOOGLE_CSE_ID environment variable.")
            raise ValueError("Google CSE ID not found")
        
        # Initialize client
        self.api_key = api_key
        self.cse_id = cse_id
        self.service = build("customsearch", "v1", developerKey=api_key)
        
        # Get configuration
        self.cse_config = config["google_cse"]
        self.results_per_page = self.cse_config.get("results_per_page", 10)
        self.max_pages = self.cse_config.get("max_pages", 3)
        
        logger.info("Google Search client initialized")
    
    @google_cse_rate_limited
    @with_exponential_backoff()
    def search(
        self,
        query: str,
        start_index: int = 1,
        num_results: int = 10,
        site_restrict: Optional[str] = None,
        language: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform a Google search using the Custom Search API.
        
        Args:
            query: Search query string.
            start_index: Start index for pagination (1-based).
            num_results: Number of results to return (max 10).
            site_restrict: Optional site restriction (e.g., "site:example.com").
            language: Optional language restriction.
            country: Optional country restriction.
            
        Returns:
            Search results dictionary.
            
        Raises:
            HttpError: If the API request fails.
        """
        try:
            # Prepare search parameters
            params: Dict[str, Any] = {
                "q": query,
                "cx": self.cse_id,
                "start": start_index,
                "num": min(num_results, 10),  # Max 10 results per request
            }
            
            # Add site restriction to query if provided
            if site_restrict:
                if not site_restrict.startswith("site:"):
                    site_restrict = f"site:{site_restrict}"
                params["q"] = f"{params['q']} {site_restrict}"
            
            # Add language restriction if provided
            if language:
                params["lr"] = f"lang_{language}"
            elif self.cse_config.get("language"):
                params["lr"] = f"lang_{self.cse_config['language']}"
            
            # Add country restriction if provided
            if country:
                params["cr"] = country
            elif self.cse_config.get("country"):
                params["cr"] = self.cse_config["country"]
            
            # Execute search
            logger.debug(f"Executing search query: {params['q']}")
            result = self.service.cse().list(**params).execute()
            
            return result
            
        except HttpError as e:
            logger.error(f"Google Search API error: {str(e)}")
            raise
    
    def search_all_pages(
        self,
        query: str,
        max_results: Optional[int] = None,
        site_restrict: Optional[str] = None,
        language: Optional[str] = None,
        country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple pages and return combined results.
        
        Args:
            query: Search query string.
            max_results: Maximum number of results to return. None for all available.
            site_restrict: Optional site restriction (e.g., "site:example.com").
            language: Optional language restriction.
            country: Optional country restriction.
            
        Returns:
            List of search result items.
        """
        # Set default max_results if not provided
        if max_results is None:
            max_results = self.results_per_page * self.max_pages
        
        all_items = []
        current_index = 1
        max_pages = self.max_pages
        
        while len(all_items) < max_results and max_pages > 0:
            try:
                # Calculate how many results to request
                num_to_request = min(10, max_results - len(all_items))
                if num_to_request <= 0:
                    break
                
                # Perform search
                result = self.search(
                    query=query,
                    start_index=current_index,
                    num_results=num_to_request,
                    site_restrict=site_restrict,
                    language=language,
                    country=country,
                )
                
                # Check if search has results
                if "items" not in result:
                    logger.info(f"No more results found for query: {query}")
                    break
                
                # Add items to results
                items = result.get("items", [])
                all_items.extend(items)
                
                # Log progress
                logger.debug(f"Retrieved {len(items)} results, total: {len(all_items)}")
                
                # Check if we've reached the end of results
                if len(items) < num_to_request:
                    logger.debug("End of results reached")
                    break
                
                # Update index for next page
                current_index += len(items)
                max_pages -= 1
                
            except Exception as e:
                logger.error(f"Error during paginated search: {str(e)}")
                break
        
        return all_items[:max_results]
    
    def search_company_jobs(
        self,
        company: str,
        keywords: List[str],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for job listings at a specific company.
        
        Args:
            company: Company name.
            keywords: List of keywords to include in the search.
            max_results: Maximum number of results to return.
            
        Returns:
            List of search result items representing job listings.
        """
        # Format search query
        keywords_str = " OR ".join([f'"{kw}"' for kw in keywords])
        query = f'"{company}" careers ({keywords_str})'
        
        logger.info(f"Searching for jobs at {company} with keywords: {keywords}")
        
        # Perform search
        results = self.search_all_pages(
            query=query,
            max_results=max_results,
        )
        
        return results
    
    def search_all_companies(
        self,
        companies: List[str],
        keywords: List[str],
        max_results_per_company: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for job listings across multiple companies.
        
        Args:
            companies: List of company names.
            keywords: List of keywords to include in the search.
            max_results_per_company: Maximum results per company.
            
        Returns:
            Dictionary mapping company names to their search results.
        """
        all_results = {}
        
        for company in companies:
            try:
                company_results = self.search_company_jobs(
                    company=company,
                    keywords=keywords,
                    max_results=max_results_per_company,
                )
                
                all_results[company] = company_results
                logger.info(f"Found {len(company_results)} job listings for {company}")
                
            except Exception as e:
                logger.error(f"Error searching for jobs at {company}: {str(e)}")
                all_results[company] = []
        
        return all_results
    
    def search_engineering_fields(
        self,
        engineering_fields: List[str],
        keywords: List[str],
        max_results_per_field: int = 20,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for job listings across engineering fields.
        
        Args:
            engineering_fields: List of engineering fields.
            keywords: List of keywords to include in the search.
            max_results_per_field: Maximum results per field.
            
        Returns:
            Dictionary mapping fields to their search results.
        """
        all_results = {}
        
        for field in engineering_fields:
            try:
                # Format search query
                keywords_str = " OR ".join([f'"{kw}"' for kw in keywords])
                query = f'"{field}" jobs ({keywords_str})'
                
                logger.info(f"Searching for jobs in {field} with keywords: {keywords}")
                
                # Perform search
                field_results = self.search_all_pages(
                    query=query,
                    max_results=max_results_per_field,
                )
                
                all_results[field] = field_results
                logger.info(f"Found {len(field_results)} job listings for {field}")
                
            except Exception as e:
                logger.error(f"Error searching for jobs in {field}: {str(e)}")
                all_results[field] = []
        
        return all_results


# Global Google Search client instance
google_search_client = GoogleSearchClient() 