from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# Simplified tweaks structure
TWEAKS = {
    "Agent-cfbu4": {},
    "ChatOutput-8jfCH": {}
}

class MessageRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {
        "message": "API is alive",
        "status": "healthy",
        "notice": "The Langflow API may take a long time to respond or time out. Please use short, simple queries."
    }

@app.post("/query")
async def query_agent(request: MessageRequest):
    logger.info(f"Query endpoint called with message: {request.message}")
    
    # Check if message is too long
    if len(request.message) > 200:
        return {
            "status": "error",
            "message": "Message is too long. Please limit your message to 200 characters to avoid timeouts."
        }
    
    application_token = os.getenv("APPLICATION_TOKEN")
    if not application_token:
        logger.error("APPLICATION_TOKEN not found")
        return {
            "status": "error",
            "message": "API configuration error: Authentication token is missing."
        }

    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    headers = {
        "Authorization": f"Bearer {application_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Simplified payload
    payload = {
        "input_value": request.message,
        "output_type": "text",
        "input_type": "text",
        "tweaks": TWEAKS
    }

    try:
        logger.info(f"Sending request to Langflow API: {api_url}")
        
        # Shorter timeout (60 seconds) since we now know it tends to time out
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        
        if response.status_code != 200:
            logger.error(f"Langflow API returned non-200 status: {response.status_code}")
            
            if response.status_code == 403:
                return {
                    "status": "error",
                    "message": "Authentication error with Langflow API. Please check your API token."
                }
            elif response.status_code == 504 or response.status_code == 502:
                return {
                    "status": "error",
                    "message": "The Langflow API timed out. Please try a shorter, simpler query or try again later."
                }
            else:
                return {
                    "status": "error",
                    "message": f"The Langflow API returned an error (status {response.status_code})."
                }
        
        # Try to parse JSON response
        try:
            response_data = response.json()
            logger.info("Successfully parsed response from Langflow API")
            
            # Extract message text (if available)
            try:
                if (response_data.get("outputs") and 
                    len(response_data["outputs"]) > 0 and 
                    response_data["outputs"][0].get("outputs") and 
                    len(response_data["outputs"][0]["outputs"]) > 0):
                    
                    return {
                        "status": "success",
                        "message": "Response received from Langflow API",
                        "data": response_data
                    }
                else:
                    return {
                        "status": "success",
                        "message": "Response received from Langflow API",
                        "data": response_data
                    }
            except Exception as e:
                logger.error(f"Error extracting message from response: {str(e)}")
                return {
                    "status": "success",
                    "message": "Response received but could not extract data",
                    "data": response_data
                }
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON response from Langflow API")
            return {
                "status": "error",
                "message": "Received invalid response from Langflow API (not valid JSON)"
            }
    
    except requests.exceptions.Timeout:
        logger.error("Request to Langflow API timed out")
        return {
            "status": "error",
            "message": "The Langflow API took too long to respond. Please try a shorter, simpler query or try again later."
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Langflow API failed: {str(e)}")
        return {
            "status": "error",
            "message": "Could not connect to the Langflow API. The service may be down or unreachable."
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "status": "error",
            "message": "An unexpected error occurred while processing your request."
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)