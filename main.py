from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json
import requests
import os
import time

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

# Simplified tweaks structure for the new flow
TWEAKS = {
    "Agent-dlR1n": {
        "max_iterations": 1,
        "max_execution_time": 60
    },
    "ChatInput-cnDzP": {},
    "ChatOutput-Ffc1R": {},
    "AstraDBToolComponent-OkQEv": {
        "limit_results": 1,
        "max_tokens": 1000
    }
}

class QueryRequest(BaseModel):
    message: str

def call_langflow_api(message: str, application_token: str) -> dict:
    """
    Call the Langflow API with error handling, logging, and retry logic
    """
    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    
    # Clean up the token and ensure proper format
    token = application_token.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "input_value": message,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": TWEAKS
    }

    max_retries = 2
    retry_delay = 30  # seconds
    attempt = 0
    
    while attempt <= max_retries:
        try:
            logger.info(f"Starting API call to Langflow (attempt {attempt + 1}/{max_retries + 1}) at: {api_url}")
            logger.info(f"With payload: {json.dumps(payload, indent=2)}")
            logger.info(f"Authorization header starts with: {headers['Authorization'][:15]}...")
            
            start_time = time.time()
            response = requests.post(api_url, json=payload, headers=headers, timeout=180)
            end_time = time.time()
            
            logger.info(f"API call took {end_time - start_time:.2f} seconds")
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            try:
                response_text = response.text
                logger.info(f"Response text: {response_text[:1000]}")  # Log first 1000 chars
            except Exception as e:
                logger.error(f"Could not read response text: {str(e)}")
            
            if response.status_code == 504:
                if attempt < max_retries:
                    logger.warning(f"Langflow API returned 504 timeout. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    attempt += 1
                    continue
                else:
                    logger.error("Langflow API timed out after all retry attempts")
                    raise HTTPException(
                        status_code=504,
                        detail=(
                            "The Langflow API is experiencing high latency and timed out after "
                            f"{max_retries + 1} attempts. This might be due to a complex query or "
                            "high system load. Please try again with a simpler query or try later."
                        )
                    )
            
            if response.status_code != 200:
                error_msg = f"Langflow API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    
                    # Check for context length exceeded error
                    if isinstance(error_detail, dict) and 'detail' in error_detail:
                        detail_str = str(error_detail['detail'])
                        if 'maximum context length' in detail_str:
                            logger.error(f"Context length exceeded: {detail_str}")
                            raise HTTPException(
                                status_code=413,  # Payload Too Large
                                detail=(
                                    "The query is generating too much data. Please try to:\n"
                                    "1. Ask about a more specific aspect of the part\n"
                                    "2. Break your question into smaller parts\n"
                                    "For example, instead of asking for all information, "
                                    "try asking specifically about the name, description, "
                                    "or a specific attribute of the part."
                                )
                            )
                    
                    error_msg += f": {json.dumps(error_detail)}"
                except:
                    error_msg += f": {response.text}"
                
                logger.error(error_msg)
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_msg
                )
            
            response_data = response.json()
            logger.info(f"Successfully parsed response JSON")
            
            # Extract the actual message from the Langflow response structure
            if (response_data.get("outputs") and 
                len(response_data["outputs"]) > 0 and 
                response_data["outputs"][0].get("outputs") and 
                len(response_data["outputs"][0]["outputs"]) > 0 and 
                response_data["outputs"][0]["outputs"][0].get("results") and 
                response_data["outputs"][0]["outputs"][0]["results"].get("message") and 
                response_data["outputs"][0]["outputs"][0]["results"]["message"].get("text")):
                
                message_text = response_data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
                return {"status": "success", "data": message_text}
            else:
                logger.warning(f"Unexpected response structure. Full response: {json.dumps(response_data, indent=2)}")
                return {"status": "success", "data": response_data}
                
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                logger.warning(f"Request timed out. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                attempt += 1
                continue
            logger.error("Request to Langflow API timed out after all retry attempts")
            raise HTTPException(
                status_code=504,
                detail=(
                    "Request timed out after 180 seconds and 3 retry attempts. "
                    "The Langflow API is taking too long to respond. This might be due to "
                    "a complex query or high system load. Please try again with a simpler "
                    "query or try later."
                )
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to Langflow API failed: {str(e)}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to communicate with Langflow API: {str(e)}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Langflow API response: {str(e)}")
            raise HTTPException(
                status_code=502,
                detail="Invalid response received from Langflow API"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred: {str(e)}"
            )
        
        attempt += 1  # Increment attempt counter if we haven't returned or continued

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