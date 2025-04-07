from openai import OpenAI
import os
from dotenv import load_dotenv
import json

def test_openai_key():
    # Load environment variables
    load_dotenv()
    
    # Get API key
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        return
    
    print(f"Testing API key: {api_key[:6]}...{api_key[-4:]}")
    
    try:
        # Initialize client without organization
        client = OpenAI(api_key=api_key)
        
        # Try a simple API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'API key is working!'"}],
            max_tokens=10
        )
        
        print("✅ Success! API key is valid")
        print(f"Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print("❌ Error: Invalid API key or API error")
        print("Error details:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        
        # Try to parse the error message for more details
        try:
            if hasattr(e, 'response'):
                error_json = e.response.json()
                print("\nFull error response:")
                print(json.dumps(error_json, indent=2))
        except:
            pass

if __name__ == "__main__":
    test_openai_key() 