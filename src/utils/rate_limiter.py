"""
Rate limiting utilities for API calls.
"""
import time
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar, cast

import backoff
from loguru import logger
from ratelimit import limits, RateLimitException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from src.utils.config import config

# Type variable for generic function
F = TypeVar('F', bound=Callable[..., Any])


class APIRateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


class APIError(Exception):
    """Base exception for API related errors."""
    pass


def rate_limited(
    calls_per_minute: int,
    name: str = "function",
    error_type: Type[Exception] = APIRateLimitError
) -> Callable[[F], F]:
    """
    Decorator to limit the rate of function calls.
    
    Args:
        calls_per_minute: Maximum number of calls allowed per minute.
        name: Name of the function or service for logging.
        error_type: Exception type to raise when rate limit is exceeded.
        
    Returns:
        Decorated function with rate limiting.
    """
    period = 60  # 1 minute in seconds
    
    def decorator(func: F) -> F:
        @limits(calls=calls_per_minute, period=period)
        def limited_func(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return limited_func(*args, **kwargs)
            except RateLimitException:
                logger.warning(f"Rate limit exceeded for {name}: {calls_per_minute} calls per minute")
                raise error_type(f"Rate limit exceeded for {name}: {calls_per_minute} calls per minute")
        
        return cast(F, wrapper)
    
    return decorator


def with_exponential_backoff(
    max_retries: int = 3,
    max_wait: int = 60,
    base_wait: int = 2,
    exception_types: tuple = (APIRateLimitError, APIError),
) -> Callable[[F], F]:
    """
    Decorator to implement exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retries.
        max_wait: Maximum wait time in seconds.
        base_wait: Base wait time for exponential calculation.
        exception_types: Exception types to retry on.
        
    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: F) -> F:
        @retry(
            retry=retry_if_exception_type(exception_types),
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=base_wait, max=max_wait),
            reraise=True,
        )
        def retry_func(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                logger.warning(f"API call failed: {str(e)}. Retrying...")
                raise
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return retry_func(*args, **kwargs)
            except RetryError as e:
                logger.error(f"Max retries exceeded: {str(e.__cause__)}")
                if e.__cause__:
                    raise e.__cause__
                raise APIError("Max retries exceeded for API call")
        
        return cast(F, wrapper)
    
    return decorator


def openai_rate_limited(func: Optional[F] = None) -> Any:
    """
    Decorator for rate limiting OpenAI API calls.
    
    If called with a function, decorates the function.
    If called without a function, returns a decorator.
    """
    rate_limit_rpm = config["openai"].get("rate_limit_rpm", 100)
    
    actual_decorator = rate_limited(
        calls_per_minute=rate_limit_rpm,
        name="OpenAI API",
        error_type=APIRateLimitError,
    )
    
    if func is None:
        return actual_decorator
    
    return actual_decorator(func)


def google_cse_rate_limited(func: Optional[F] = None) -> Any:
    """
    Decorator for rate limiting Google Custom Search API calls.
    
    If called with a function, decorates the function.
    If called without a function, returns a decorator.
    """
    rate_limit_rpm = config["google_cse"].get("rate_limit_rpm", 60)
    
    actual_decorator = rate_limited(
        calls_per_minute=rate_limit_rpm,
        name="Google CSE API",
        error_type=APIRateLimitError,
    )
    
    if func is None:
        return actual_decorator
    
    return actual_decorator(func) 