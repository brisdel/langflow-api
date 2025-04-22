from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json
import requests
import os
import time
import re

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants for Langflow API
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "ed6c45f6-6029-47a5-a6ee-86d7caf24d60"
FLOW_ID = "3a762c3b-63a1-4815-9a7c-bdb9634b63fa"
FOLDER_ID = "0c08b713-d6fc-43ed-aff9-ebd1116ebb95"

# Minimal tweaks structure focusing only on the database query
TWEAKS = {
    "AstraDBToolComponent-OkQEv": {
        "query": None  # Will be set dynamically
    }
}

class QueryRequest(BaseModel):
    message: str

def extract_part_number(message: str) -> str:
    """Extract part number from message"""
    match = re.search(r'PA-\d+', message)
    return match.group(0) if match else None

def call_langflow_api(message: str, application_token: str) -> dict:
    """
    Call the Langflow API using verified configuration
    """
    # Extract part number
    part_number = extract_part_number(message)
    if not part_number:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid part number in the format PA-XXXXX"
        )

    # Construct the URL using the API run endpoint structure
    url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}?stream=false"
    
    logger.info(f"Making request to URL: {url}")

    # Clean up the token and ensure proper format
    token = application_token.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    # Headers matching the official Langflow snippet
    headers = {
        "Content-Type": "application/json",
        # "accept": "application/json", # Removed as not present in snippet
        "Authorization": token
    }

    # Payload matching the official Langflow snippet format
    payload = {
        "input_value": message, # Use the original message
        "output_type": "chat",
        "input_type": "chat"
        # "tweaks": {} # Keeping tweaks empty for now
    }

    logger.info(f"Making request with payload: {json.dumps(payload, indent=2)}")
    logger.info(f"Using headers: {json.dumps({k: v if k != 'Authorization' else '[REDACTED]' for k, v in headers.items()}, indent=2)}")

    try:
        # Send request with a longer timeout since we're seeing context length issues
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        response_data = response.json()
        logger.info(f"Received response: {json.dumps(response_data, indent=2)}")
        
        # Extract the actual text response if available
        if isinstance(response_data, dict):
            try:
                # Navigate through the response structure to get the text
                if (response_data.get("output") and 
                    isinstance(response_data["output"], list) and 
                    len(response_data["output"]) > 0):
                    return {"status": "success", "data": response_data["output"][0]}
            except:
                pass
        
        return {"status": "success", "data": response_data}
        
    except requests.exceptions.Timeout:
        logger.error("Request to Langflow API timed out")
        raise HTTPException(
            status_code=504,
            detail="Request timed out. Please try again."
        )
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {str(e)}")
        # Extract error message from response if possible
        try:
            error_detail = e.response.json()
            error_message = error_detail.get('detail', str(e))
            
            # Check specifically for context length error
            if "context length" in str(error_message).lower():
                raise HTTPException(
                    status_code=413,
                    detail="The query is too complex. Please try a simpler query or break it into smaller parts."
                )
        except:
            error_message = str(e)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Langflow API error: {error_message}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.get("/")
def root():
    """Health check endpoint that also verifies environment variables and Langflow API connection"""
    try:
        # Check environment variables
        application_token = os.getenv("APPLICATION_TOKEN")
        if not application_token:
            return {
                "status": "warning",
                "message": "API is running but APPLICATION_TOKEN is not configured",
                "environment": {
                    "port": os.getenv("PORT"),
                    "has_token": False
                }
            }

        # Test Langflow API connection
        test_url = f"{BASE_API_URL}/health"  # Assuming there's a health endpoint, if not we'll use the main URL
        try:
            response = requests.get(test_url, timeout=5)
            langflow_status = "connected" if response.status_code == 200 else f"error (status: {response.status_code})"
        except requests.exceptions.RequestException as e:
            langflow_status = f"connection failed ({str(e)})"

        return {
            "status": "healthy",
            "message": "API is alive",
            "environment": {
                "port": os.getenv("PORT"),
                "has_token": bool(application_token),
                "token_length": len(application_token) if application_token else 0,
                "langflow_api_status": langflow_status
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "timestamp": time.time()
        }

@app.post("/query")
async def query(request: QueryRequest):
    """
    Process a query using the Langflow API
    """
    try:
        logger.info(f"Received query request with message: {request.message}")
        
        # Get the application token from environment
        application_token = os.getenv("APPLICATION_TOKEN")
        if not application_token:
            logger.error("APPLICATION_TOKEN not found in environment variables")
            raise HTTPException(
                status_code=500,
                detail="APPLICATION_TOKEN is not configured on the server"
            )
        
        # Verify Langflow API is accessible before making the main request
        try:
            test_url = f"{BASE_API_URL}/health"  # Assuming there's a health endpoint
            requests.get(test_url, timeout=5)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Langflow API: {str(e)}")
            raise HTTPException(
                status_code=502,
                detail=f"Cannot establish connection to Langflow API. Please try again later. Error: {str(e)}"
            )
        
        # Call Langflow API
        response = call_langflow_api(request.message, application_token)
        
        logger.info("Successfully processed query")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while processing your request: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port) 