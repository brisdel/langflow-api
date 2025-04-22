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

    # Payload matching the official Langflow snippet format, plus tweaks based on component config
    payload = {
        "input_value": message, # Use the original message
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": {
            "AstraDBToolComponent-OkQEv": { # Target the specific tool component
                # Pass the parameter name from the component's (deprecated) tool_params
                "partreferencenumber": part_number
            }
        }
    }

    logger.info(f"Making request with payload: {json.dumps(payload, indent=2)}")
    logger.info(f"Using headers: {json.dumps({k: v if k != 'Authorization' else '[REDACTED]' for k, v in headers.items()}, indent=2)}")

    try:
        # Send request with a longer timeout since we're seeing context length issues
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        response_data = response.json()
        logger.info(f"Received response: {json.dumps(response_data, indent=2)}")

        # Updated logic to parse the correct nested structure
        try:
            logger.info("Attempting to parse Langflow response...")
            final_output_list = response_data.get("outputs", [])
            if not final_output_list or not isinstance(final_output_list, list):
                logger.warning("'outputs' key missing or not a list in response.")
                raise ValueError("Missing or invalid 'outputs' list")

            logger.info(f"Found top-level 'outputs' list with {len(final_output_list)} item(s).")
            first_output_item = final_output_list[0]
            if not isinstance(first_output_item, dict):
                logger.warning("First item in 'outputs' is not a dictionary.")
                raise ValueError("Invalid first item in 'outputs' list")

            nested_output_list = first_output_item.get("outputs", [])
            if not nested_output_list or not isinstance(nested_output_list, list):
                logger.warning("Nested 'outputs' key missing or not a list in first output item.")
                raise ValueError("Missing or invalid nested 'outputs' list")

            logger.info(f"Found nested 'outputs' list with {len(nested_output_list)} item(s).")
            first_nested_output_item = nested_output_list[0]
            if not isinstance(first_nested_output_item, dict):
                logger.warning("First item in nested 'outputs' is not a dictionary.")
                raise ValueError("Invalid first item in nested 'outputs' list")

            results_dict = first_nested_output_item.get("results", {})
            if not results_dict or not isinstance(results_dict, dict):
                 logger.warning("'results' key missing or not a dict in nested output item.")
                 raise ValueError("Missing or invalid 'results' dict")

            message_dict = results_dict.get("message", {})
            if not message_dict or not isinstance(message_dict, dict):
                 logger.warning("'message' key missing or not a dict in results.")
                 raise ValueError("Missing or invalid 'message' dict")

            final_text = message_dict.get("text")
            if final_text and isinstance(final_text, str):
                logger.info(f"Successfully extracted text: {final_text}")
                return {"status": "success", "data": {"response": final_text}}
            else:
                logger.warning("'text' key missing or not a string in message dict.")
                raise ValueError("Missing or invalid 'text' value")

        except Exception as e:
            logger.error(f"Error parsing Langflow response: {e}. Returning raw data.", exc_info=True)
            # Return raw data even if parsing fails
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