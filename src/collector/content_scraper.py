"""
Web scraper for extracting job content from search results.
"""
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import html2text
import requests
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.config import config
from src.utils.rate_limiter import with_exponential_backoff


class ContentScraper:
    """
    Scraper for extracting job content from web pages.
    
    Handles fetching pages and extracting relevant job information.
    """
    
    def __init__(self):
        """Initialize the content scraper."""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        # HTML to text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_tables = False
        
        logger.info("Content scraper initialized")
    
    @with_exponential_backoff(max_retries=3, max_wait=30, base_wait=2)
    def fetch_url(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Fetch content from a URL.
        
        Args:
            url: URL to fetch.
            timeout: Timeout in seconds.
            
        Returns:
            HTML content string or None if fetch failed.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            
            # Check if response is HTML
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower():
                logger.warning(f"URL {url} returned non-HTML content: {content_type}")
                return None
            
            # Try to get encoding from response, fallback to utf-8
            response.encoding = response.apparent_encoding or "utf-8"
            
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            return None
    
    def extract_job_content(self, html: str) -> Tuple[str, Dict[str, str]]:
        """
        Extract job content from HTML.
        
        Args:
            html: HTML content string.
            
        Returns:
            Tuple of (extracted text content, metadata dictionary).
        """
        metadata = {}
        soup = BeautifulSoup(html, "lxml")
        
        # Try to extract title
        title_tag = soup.find("title")
        if title_tag:
            metadata["page_title"] = title_tag.text.strip()
        
        # Try to extract job title from common patterns
        job_title = None
        
        # Try h1 first, as it's often the job title
        h1_tags = soup.find_all("h1")
        if h1_tags:
            job_title = h1_tags[0].text.strip()
            metadata["title"] = job_title
        
        # Look for common job title containers
        title_containers = soup.select(".job-title, .posting-title, .career-title, h1.title")
        if title_containers:
            job_title = title_containers[0].text.strip()
            metadata["title"] = job_title
        
        # Extract company if available
        company_containers = soup.select(".company-name, .employer, [itemprop='hiringOrganization']")
        if company_containers:
            metadata["company"] = company_containers[0].text.strip()
        
        # Extract location if available
        location_containers = soup.select(".location, [itemprop='jobLocation'], .job-location")
        if location_containers:
            metadata["location"] = location_containers[0].text.strip()
        
        # Try to extract main content
        # First, look for common job content containers
        content_selectors = [
            "#job-description",
            ".job-description",
            ".description",
            "#job-details",
            ".job-details",
            ".jobDesc",
            "[itemprop='description']",
            ".career-details",
            ".posting-body",
        ]
        
        main_content = None
        
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                main_content = container
                break
        
        # If we couldn't find a specific container, use the main body
        if not main_content:
            # Remove header, nav, footer, scripts, and other non-content elements
            for tag in soup.select("header, nav, footer, script, style, .header, .footer, .navigation"):
                tag.decompose()
            
            # Use the body as main content
            main_content = soup.find("body")
        
        # Convert to text
        if main_content:
            # Clean up the content first
            for tag in main_content.select("script, style"):
                tag.decompose()
            
            # Use HTML2Text to convert to markdown-like text
            text_content = self.html_converter.handle(str(main_content))
            
            # Clean up the text
            text_content = re.sub(r'\n{3,}', '\n\n', text_content)  # Remove excessive newlines
            text_content = text_content.strip()
        else:
            # Fall back to converting the entire page
            logger.warning("Could not find main content container, using full page")
            text_content = self.html_converter.handle(html)
        
        return text_content, metadata
    
    def identify_job_site(self, url: str) -> Optional[str]:
        """
        Identify the job site or company career page from URL.
        
        Args:
            url: URL to identify.
            
        Returns:
            Site identifier or None if unknown.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Check for known job sites
        job_sites = {
            "linkedin.com": "LinkedIn",
            "indeed.com": "Indeed",
            "glassdoor.com": "Glassdoor",
            "monster.com": "Monster",
            "careerbuilder.com": "CareerBuilder",
            "dice.com": "Dice",
            "ziprecruiter.com": "ZipRecruiter",
            "simplyhired.com": "SimplyHired",
            "lever.co": "Lever",
            "greenhouse.io": "Greenhouse",
            "workday.com": "Workday",
        }
        
        for site_domain, site_name in job_sites.items():
            if site_domain in domain:
                return site_name
        
        # If not a known job site, try to extract company name from domain
        domain_parts = domain.split(".")
        if len(domain_parts) > 1:
            return domain_parts[-2].capitalize()  # e.g., google.com -> Google
        
        return None
    
    def scrape_search_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Scrape content from a Google search result item.
        
        Args:
            result: Google search result item.
            
        Returns:
            Dictionary with scraped job content or None if scraping failed.
        """
        try:
            # Extract URL and title from search result
            url = result.get("link")
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            
            if not url:
                logger.warning("Search result has no URL, skipping")
                return None
            
            # Fetch page content
            logger.info(f"Scraping job content from: {url}")
            html = self.fetch_url(url)
            
            if not html:
                logger.warning(f"Failed to fetch content from {url}")
                return None
            
            # Extract job content
            content, metadata = self.extract_job_content(html)
            
            # Identify source
            source = self.identify_job_site(url)
            
            # Create job listing object
            job_listing = {
                "url": url,
                "title": metadata.get("title", title),
                "content": content,
                "snippet": snippet,
                "source": source,
                "company": metadata.get("company", ""),
                "location": metadata.get("location", ""),
                "collected_at": time.time(),
                "search_metadata": {
                    "search_title": result.get("title"),
                    "search_snippet": result.get("snippet"),
                    "display_link": result.get("displayLink"),
                },
                "page_metadata": metadata,
            }
            
            logger.info(f"Successfully scraped job content from: {url}")
            return job_listing
            
        except Exception as e:
            logger.error(f"Error scraping search result: {str(e)}")
            return None
    
    def scrape_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scrape content from multiple search results.
        
        Args:
            results: List of Google search result items.
            
        Returns:
            List of scraped job listings.
        """
        scraped_listings = []
        
        for result in results:
            try:
                # Add delay between requests to avoid being blocked
                time.sleep(2)
                
                listing = self.scrape_search_result(result)
                if listing:
                    scraped_listings.append(listing)
                
            except Exception as e:
                logger.error(f"Error scraping result {result.get('link')}: {str(e)}")
        
        logger.info(f"Scraped {len(scraped_listings)} job listings from {len(results)} search results")
        return scraped_listings


# Global content scraper instance
content_scraper = ContentScraper() 