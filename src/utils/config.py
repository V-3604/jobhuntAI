"""
Configuration utilities for loading and managing application settings.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
load_dotenv()

# Define base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"


def load_yaml_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the YAML config file. If None, uses the default config path.
        
    Returns:
        Dictionary containing the configuration.
        
    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the config file is invalid YAML.
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.debug(f"Loaded configuration from {config_path}")
        return config
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise


def get_env_variable(name: str, default: Optional[Any] = None) -> Any:
    """
    Get an environment variable or return a default value.
    
    Args:
        name: Name of the environment variable.
        default: Default value to return if the environment variable is not set.
        
    Returns:
        The value of the environment variable or the default value.
    """
    value = os.getenv(name, default)
    if value is None:
        logger.warning(f"Environment variable {name} not set, using None as default")
    elif isinstance(value, str):
        # Clean up the value by removing any comments
        value = value.split('#')[0].strip()
    return value


def get_merged_config() -> Dict[str, Any]:
    """
    Get a merged configuration from YAML and environment variables.
    Environment variables take precedence over YAML configuration.
    
    Returns:
        Dictionary containing the merged configuration.
    """
    # Load YAML configuration
    config = load_yaml_config()
    
    # Override with environment variables
    # Database
    config['database']['connection_string'] = get_env_variable(
        'MONGODB_URI', 
        config['database']['connection_string']
    )
    config['database']['database_name'] = get_env_variable(
        'MONGODB_DB_NAME', 
        config['database']['database_name']
    )
    
    # OpenAI
    config['openai']['default_model'] = get_env_variable(
        'OPENAI_MODEL', 
        config['openai']['default_model']
    )
    
    # Google CSE
    # These are required, so don't provide defaults
    google_api_key = get_env_variable('GOOGLE_API_KEY')
    google_cse_id = get_env_variable('GOOGLE_CSE_ID')
    
    if google_api_key:
        config['google_cse']['api_key'] = google_api_key
    else:
        logger.warning("GOOGLE_API_KEY not set, Google CSE functionality may be limited")
    
    if google_cse_id:
        config['google_cse']['cse_id'] = google_cse_id
    else:
        logger.warning("GOOGLE_CSE_ID not set, Google CSE functionality may be limited")
    
    # API settings
    config['api']['host'] = get_env_variable('API_HOST', config['api']['host'])
    config['api']['port'] = int(get_env_variable('API_PORT', config['api']['port']))
    config['api']['enable_cors'] = get_env_variable('ENABLE_CORS', 'true').lower() == 'true'
    
    # Logging
    config['logging']['level'] = get_env_variable('LOG_LEVEL', config['logging']['level'])
    
    # Rate limits
    openai_rpm = get_env_variable('OPENAI_RPM')
    google_rpm = get_env_variable('GOOGLE_RPM')
    
    if openai_rpm:
        # Remove any comments from the value
        openai_rpm = openai_rpm.split('#')[0].strip()
        config['openai']['rate_limit_rpm'] = int(openai_rpm)
    if google_rpm:
        # Remove any comments from the value
        google_rpm = google_rpm.split('#')[0].strip()
        config['google_cse']['rate_limit_rpm'] = int(google_rpm)
    
    return config


# Default configuration instance
config = get_merged_config() 