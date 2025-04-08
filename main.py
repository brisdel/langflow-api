from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests
import os
import logging
import json
import sys

# Configure logging with more detail
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# Constants
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "ed6c45f6-6029-47a5-a6ee-86d7caf24d60"
FLOW_ID = "c4369450-5685-4bb4-85b3-f47b7dd0e917"

TWEAKS = {
    "Agent-cfbu4": {},
    "ChatInput-URWrQ": {},
    "ChatOutput-8jfCH": {},
    "AstraDBToolComponent-HX1wm": {},
    "AstraDB-1zteC": {},
    "ParseDataFrame-uutq1": {},
    "DataToDataFrame-cLytb": {},
    "Prompt-BPTjL": {},
    "Prompt-k5ksd": {},
    "Agent-GEpuC": {},
    "DeepSeekModelComponent-boSdy": {}
}

class MessageRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {
        "message": "API is alive",
        "status": "healthy"
    }

@app.post("/query")
async def query_agent(request: MessageRequest):
    logger.info(f"Query endpoint called with message: {request.message}")
    
    # Print complete request for debugging
    logger.info(f"Complete request object: {request}")
    
    # Dynamically load the token
    application_token = os.getenv("APPLICATION_TOKEN")
    if not application_token:
        logger.error("APPLICATION_TOKEN not found in environment variables")
        return {
            "status": "error",
            "message": "APPLICATION_TOKEN is not set"
        }
    
    # Log token length for verification (don't log the actual token)
    logger.info(f"APPLICATION_TOKEN length: {len(application_token)}")

    # Construct API URL
    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    logger.info(f"API URL: {api_url}")
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {application_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Prepare payload
    payload = {
        "input_value": request.message,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": TWEAKS
    }
    
    logger.info(f"Payload: {json.dumps(payload)}")
    
    try:
        # Make direct API request first to test connectivity
        logger.info("Attempting to make a direct test request to Langflow API")
        direct_response = requests.get(f"{BASE_API_URL}/health", timeout=10)
        logger.info(f"Direct test response status: {direct_response.status_code}")
        logger.info(f"Direct test response content: {direct_response.text[:100]}")  # Log first 100 chars
        
        # Now make the actual request
        logger.info(f"Sending main request to Langflow API: {api_url}")
        response = requests.post(
            api_url, 
            json=payload, 
            headers=headers, 
            timeout=180  # 3-minute timeout
        )
        
        # Log detailed response info for debugging
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        if response.content:
            content_preview = response.content[:200].decode('utf-8', errors='replace')
            logger.info(f"Response content (first 200 chars): {content_preview}")
        else:
            logger.info("Response content is empty")
            
        # Handle empty responses
        if not response.content:
            return {
                "status": "error",
                "message": "Empty response from Langflow API"
            }
            
        # Check status code
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Langflow API returned status {response.status_code}",
                "details": response.text
            }

        # Try to parse as JSON
        try:
            response_data = response.json()
            logger.info("Successfully parsed response as JSON")
            
            # Try to extract the message from the nested structure
            try:
                if (response_data.get("outputs") and 
                    len(response_data["outputs"]) > 0 and 
                    response_data["outputs"][0].get("outputs") and 
                    len(response_data["outputs"][0]["outputs"]) > 0 and
                    response_data["outputs"][0]["outputs"][0].get("results") and
                    response_data["outputs"][0]["outputs"][0]["results"].get("message") and
                    response_data["outputs"][0]["outputs"][0]["results"]["message"].get("text")):
                    
                    message_text = response_data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
                    
                    return {
                        "status": "success",
                        "message": message_text
                    }
                else:
                    logger.info("Could not extract message text from nested structure, returning full response")
                    return {
                        "status": "success",
                        "response": response_data
                    }
            except Exception as extract_error:
                logger.error(f"Error extracting message from response: {str(extract_error)}")
                return {
                    "status": "success",
                    "response": response_data,
                    "extraction_error": str(extract_error)
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {str(e)}")
            return {
                "status": "error",
                "message": "Invalid JSON response from Langflow API",
                "raw_response": response.text[:1000] if response.text else "Empty response"
            }
            
    except requests.exceptions.Timeout:
        logger.error("Request to Langflow API timed out")
        return {
            "status": "error",
            "message": "Request timed out. The Langflow API is taking too long to respond."
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Langflow API failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Request to Langflow API failed: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "error_type": str(type(e).__name__)
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)