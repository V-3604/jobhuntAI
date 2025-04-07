"""
JSON utilities for consistent encoding across the application.
"""
import json
from datetime import datetime

from bson import ObjectId


class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle MongoDB ObjectId and datetime objects.
    
    This encoder ensures consistent JSON serialization across the application,
    particularly for MongoDB-specific types and datetime objects.
    """
    
    def default(self, obj):
        """
        Encode MongoDB ObjectId and datetime objects.
        
        Args:
            obj: Object to encode.
            
        Returns:
            JSON-serializable representation of the object.
        """
        if isinstance(obj, ObjectId):
            return str(obj)
        if hasattr(obj, 'isoformat'):  # For datetime objects
            return obj.isoformat()
        return super().default(obj)


def dumps(obj, indent=None, **kwargs):
    """
    Serialize object to JSON string with consistent encoding.
    
    Args:
        obj: Object to serialize.
        indent: Indentation level for pretty printing.
        **kwargs: Additional keyword arguments for json.dumps.
        
    Returns:
        JSON string representation of the object.
    """
    return json.dumps(obj, cls=JSONEncoder, indent=indent, **kwargs)


def loads(json_str, **kwargs):
    """
    Deserialize JSON string to Python object.
    
    Args:
        json_str: JSON string to deserialize.
        **kwargs: Additional keyword arguments for json.loads.
        
    Returns:
        Python object representation of the JSON string.
    """
    return json.loads(json_str, **kwargs) 