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
    Call the Langflow API using the standard structure
    """
    # Extract part number
    part_number = extract_part_number(message)
    if not part_number:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid part number in the format PA-XXXXX"
        )

    # Construct the URL exactly as in the example
    url = f"https://api.langflow.astra.datastax.com/lf/ed6c45f6-6029-47a5-a6ee-86d7caf24d60/api/v1/run/3a762c3b-63a1-4815-9a7c-bdb9634b63fa"

    # Clean up the token and ensure proper format
    token = application_token.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    # Headers exactly as in the example
    headers = {
        "Content-Type": "application/json",
        "Authorization": token
    }

    # Basic payload structure as in the example
    payload = {
        "input_value": f"What is the name of part {part_number}?",
        "output_type": "chat",
        "input_type": "chat"
    }

    logger.info(f"Making request to Langflow API with payload: {json.dumps(payload, indent=2)}")

    try:
        # Send API request exactly as in the example
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        
        response_data = response.json()
        logger.info(f"Received response: {json.dumps(response_data, indent=2)}")
        
        return {"status": "success", "data": response_data}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making API request: {str(e)}")
        if isinstance(e, requests.exceptions.Timeout):
            raise HTTPException(
                status_code=504,
                detail="Request timed out. Please try again."
            )
        elif isinstance(e, requests.exceptions.HTTPError):
            # Check if it's a context length error
            try:
                error_detail = e.response.json()
                if isinstance(error_detail, dict) and 'detail' in error_detail:
                    detail_str = str(error_detail['detail'])
                    if 'maximum context length' in detail_str:
                        raise HTTPException(
                            status_code=413,
                            detail="Unable to process query due to size limitations. Please contact support."
                        )
            except:
                pass
            raise HTTPException(
                status_code=e.response.status_code if hasattr(e.response, 'status_code') else 500,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error making API request: {str(e)}"
            )
    except ValueError as e:
        logger.error(f"Error parsing response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing response: {str(e)}"
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