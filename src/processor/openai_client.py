"""
OpenAI API client for job processing tasks.
"""
import os
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from openai import OpenAI
from openai.types.chat import ChatCompletion
from openai.types.embedding import Embedding

from src.utils.config import config
from src.utils.rate_limiter import openai_rate_limited, with_exponential_backoff


class OpenAIClient:
    """
    Client for OpenAI API integration.
    
    Handles chat completions and embeddings for job data processing.
    """
    
    def __init__(self):
        """Initialize the OpenAI client."""
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
            raise ValueError("OpenAI API key not found")
        
        # Get optional organization ID
        org_id = os.getenv("OPENAI_ORG_ID")
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=api_key,
            organization=org_id
        )
        
        # Get configuration
        self.openai_config = config["openai"]
        self.default_model = self.openai_config["default_model"]
        self.fallback_model = self.openai_config.get("fallback_model", "gpt-4")
        self.embedding_model = self.openai_config.get("embedding_model", "text-embedding-3-large")
        self.max_tokens = self.openai_config.get("max_tokens", 4096)
        self.temperature = self.openai_config.get("temperature", 0.2)
        
        logger.info(f"OpenAI client initialized with model {self.default_model}")
    
    @openai_rate_limited
    @with_exponential_backoff()
    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[Union[str, Dict[str, str]]] = None,
    ) -> ChatCompletion:
        """
        Generate a chat completion using OpenAI's API.
        
        Args:
            messages: List of message objects for the conversation.
            model: Model to use for generation. Defaults to self.default_model.
            temperature: Temperature for generation. Defaults to self.temperature.
            max_tokens: Maximum tokens to generate. Defaults to self.max_tokens.
            functions: List of function definitions (for function calling).
            function_call: Function call parameter.
            
        Returns:
            OpenAI chat completion response.
            
        Raises:
            Exception: If the API call fails.
        """
        try:
            # Set defaults if not provided
            model = model or self.default_model
            temperature = temperature if temperature is not None else self.temperature
            max_tokens = max_tokens or self.max_tokens
            
            # Prepare parameters
            params: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            # Add function calling parameters if provided
            if functions:
                params["tools"] = [{"type": "function", "function": func} for func in functions]
            
            if function_call:
                if isinstance(function_call, str):
                    params["tool_choice"] = {"type": "function", "function": {"name": function_call}}
                else:
                    params["tool_choice"] = {"type": "function", "function": function_call}
            
            # Make API call
            response = self.client.chat.completions.create(**params)
            
            return response
        
        except Exception as e:
            logger.error(f"Error generating chat completion: {str(e)}")
            
            # Try with fallback model if available
            if model != self.fallback_model and self.fallback_model:
                logger.info(f"Retrying with fallback model {self.fallback_model}")
                params["model"] = self.fallback_model
                try:
                    response = self.client.chat.completions.create(**params)
                    return response
                except Exception as fallback_error:
                    logger.error(f"Error with fallback model: {str(fallback_error)}")
            
            # Re-raise the original exception
            raise
    
    @openai_rate_limited
    @with_exponential_backoff()
    def generate_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """
        Generate embeddings for text inputs.
        
        Args:
            texts: List of text strings to generate embeddings for.
            model: Model to use for embeddings. Defaults to self.embedding_model.
            
        Returns:
            List of embedding vectors.
            
        Raises:
            Exception: If the API call fails.
        """
        try:
            # Set default model if not provided
            model = model or self.embedding_model
            
            # Make API call
            response = self.client.embeddings.create(
                model=model,
                input=texts,
                encoding_format="float"
            )
            
            # Extract embedding vectors from response
            embeddings = [embedding.embedding for embedding in response.data]
            
            return embeddings
        
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    def extract_entity(
        self, 
        text: str, 
        entity_type: str,
        additional_instructions: Optional[str] = None,
    ) -> Any:
        """
        Extract a specific entity from job listing text.
        
        Args:
            text: Text to extract entity from.
            entity_type: Type of entity to extract (e.g., "company", "skills", "field").
            additional_instructions: Optional additional instructions for extraction.
            
        Returns:
            Extracted entity or entities.
        """
        # Create prompt
        base_prompt = f"Extract the {entity_type} from the following job listing."
        if additional_instructions:
            base_prompt += f"\n\n{additional_instructions}"
        
        messages = [
            {"role": "system", "content": base_prompt},
            {"role": "user", "content": text}
        ]
        
        # Make API call
        response = self.generate_chat_completion(
            messages=messages,
            temperature=0.1,  # Lower temperature for more deterministic results
        )
        
        # Extract result
        result = response.choices[0].message.content
        
        return result
    
    def classify_job_field(self, job_description: str) -> str:
        """
        Classify a job description into an engineering field.
        
        Args:
            job_description: Job description text.
            
        Returns:
            Classified engineering field.
        """
        # List of engineering fields from config
        engineering_fields = config["collection"]["engineering_fields"]
        fields_str = "\n".join([f"- {field}" for field in engineering_fields])
        
        # Create prompt
        prompt = (
            "Classify the following job description into one of these engineering fields:\n\n"
            f"{fields_str}\n\n"
            "If the job doesn't fit any of these fields well, choose the closest match. "
            "Respond with ONLY the exact name of the field from the list above, nothing else."
        )
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": job_description}
        ]
        
        # Make API call
        response = self.generate_chat_completion(
            messages=messages,
            temperature=0.1,  # Lower temperature for more deterministic results
        )
        
        # Extract result
        field = response.choices[0].message.content.strip()
        
        # Validate result is in the list of fields
        if field not in engineering_fields:
            logger.warning(f"Classified field '{field}' not in predefined list, using 'Other'")
            field = "Other"
        
        return field
    
    def extract_skills(self, job_description: str) -> List[str]:
        """
        Extract required skills from a job description.
        
        Args:
            job_description: Job description text.
            
        Returns:
            List of extracted skills.
        """
        # Create prompt
        prompt = (
            "Extract all technical and professional skills required for this job. "
            "Format the output as a Python list of strings, each representing a single skill. "
            "Include both hard technical skills and important soft skills. "
            "Be specific but concise with each skill."
        )
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": job_description}
        ]
        
        # Make API call
        response = self.generate_chat_completion(
            messages=messages,
            temperature=0.1,  # Lower temperature for more deterministic results
        )
        
        # Extract and parse result
        skills_text = response.choices[0].message.content.strip()
        
        # Try to parse as Python list
        try:
            # Extract content from square brackets if present
            if "[" in skills_text and "]" in skills_text:
                skills_text = skills_text[skills_text.find("["):skills_text.rfind("]")+1]
            
            # Try to parse as Python literal
            import ast
            skills = ast.literal_eval(skills_text)
            
            # Ensure it's a list of strings
            if not isinstance(skills, list):
                raise ValueError("Not a list")
            
            skills = [str(skill).strip() for skill in skills if skill]
            
        except (SyntaxError, ValueError):
            # Fallback: Split by commas and clean up
            logger.warning("Failed to parse skills as Python list, using fallback parsing")
            skills = [skill.strip() for skill in skills_text.split(",")]
            skills = [skill.strip('"\'[]') for skill in skills]
            skills = [skill for skill in skills if skill]
        
        return skills
    
    def extract_job_metadata(self, job_description: str) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from a job description.
        
        Args:
            job_description: Job description text.
            
        Returns:
            Dictionary of extracted metadata.
        """
        # Create prompt
        prompt = """
        Extract the following information from the job listing in JSON format:
        
        {
            "title": "Job title",
            "company": "Company name",
            "location": "Job location(s)",
            "job_type": "Full-time, Part-time, Contract, etc.",
            "experience_level": "Entry-level, Mid-level, Senior, etc.",
            "required_skills": ["List", "of", "required", "skills"],
            "preferred_skills": ["List", "of", "preferred", "skills"],
            "education_requirements": "Education requirements",
            "salary_range": "Salary range if provided",
            "engineering_field": "Most relevant engineering field",
            "remote_policy": "Remote work policy if specified"
        }
        
        If information for a field is not provided, use null or an empty list as appropriate.
        Respond with ONLY valid JSON, no additional text.
        """
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": job_description}
        ]
        
        # Make API call
        response = self.generate_chat_completion(
            messages=messages,
            temperature=0.1,  # Lower temperature for more deterministic results
        )
        
        # Extract result
        result = response.choices[0].message.content.strip()
        
        # Parse JSON
        try:
            import json
            metadata = json.loads(result)
            
            # Ensure engineering field is from our list
            if "engineering_field" in metadata and metadata["engineering_field"]:
                engineering_fields = config["collection"]["engineering_fields"]
                if metadata["engineering_field"] not in engineering_fields:
                    # Get a proper classification
                    metadata["engineering_field"] = self.classify_job_field(job_description)
            
            return metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {str(e)}")
            # Return empty metadata
            return {}
    
    def compare_listings_for_similarity(self, listing1: str, listing2: str) -> float:
        """
        Compare two job listings for similarity.
        
        Args:
            listing1: First job listing text.
            listing2: Second job listing text.
            
        Returns:
            Similarity score between 0 and 1.
        """
        # Create prompt
        prompt = """
        Compare these two job listings and rate their similarity on a scale from 0 to 1, where:
        - 0 means completely different jobs
        - 1 means identical jobs or obvious duplicates
        
        Consider:
        - Job titles
        - Companies
        - Required skills
        - Job descriptions
        - Responsibilities
        
        Return ONLY the numeric similarity score between 0 and 1, nothing else.
        """
        
        combined_text = f"Job Listing 1:\n{listing1}\n\nJob Listing 2:\n{listing2}"
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": combined_text}
        ]
        
        # Make API call
        response = self.generate_chat_completion(
            messages=messages,
            temperature=0.1,  # Lower temperature for more deterministic results
        )
        
        # Extract result
        result = response.choices[0].message.content.strip()
        
        try:
            # Parse to float
            similarity = float(result)
            # Ensure value is between 0 and 1
            similarity = max(0.0, min(1.0, similarity))
            return similarity
        except ValueError:
            logger.error(f"Failed to parse similarity score: {result}")
            return 0.0


# Global OpenAI client instance
openai_client = OpenAIClient() 