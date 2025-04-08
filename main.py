from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import logging
import json
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "ed6c45f6-6029-47a5-a6ee-86d7caf24d60"
FLOW_ID = "c4369450-5685-4bb4-85b3-f47b7dd0e917"

# Tweaks structure
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

# Request body model
class QueryRequest(BaseModel):
    message: str

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Verify environment variables
    application_token = os.getenv("APPLICATION_TOKEN")
    if not application_token:
        logger.error("APPLICATION_TOKEN not found in environment variables!")
    else:
        logger.info("APPLICATION_TOKEN found in environment variables")
    
    port = os.getenv("PORT")
    logger.info(f"PORT configured as: {port}")

# Health check route
@app.get("/")
async def root():
    logger.info("Health check endpoint called")
    return {
        "status": "healthy",
        "message": "API is alive",
        "environment": {
            "port": os.getenv("PORT"),
            "has_token": bool(os.getenv("APPLICATION_TOKEN"))
        }
    }

# Langflow query route
@app.post("/query")
async def query_agent(request: QueryRequest):
    logger.info(f"Query endpoint called with message: {request.message}")
    
    # Dynamically load the token
    application_token = os.getenv("APPLICATION_TOKEN")

    if not application_token:
        logger.error("APPLICATION_TOKEN not found")
        return {
            "status": "error",
            "message": "APPLICATION_TOKEN is not set in environment variables."
        }

    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    headers = {
        "Authorization": f"Bearer {application_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "input_value": request.message,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": TWEAKS
    }

    try:
        logger.info(f"Sending request to Langflow API: {api_url}")
        
        # Increase timeout to 3 minutes (180 seconds)
        response = requests.post(api_url, json=payload, headers=headers, timeout=180)
        
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error response from Langflow: {response.text}")
            return {
                "status": "error",
                "message": f"Langflow API returned status {response.status_code}",
                "details": response.text
            }

        # Try to parse the response JSON
        try:
            response_data = response.json()
            
            # Extract the actual message text from the response structure
            if (response_data.get("outputs") and 
                len(response_data["outputs"]) > 0 and 
                response_data["outputs"][0].get("outputs") and 
                len(response_data["outputs"][0]["outputs"]) > 0 and 
                response_data["outputs"][0]["outputs"][0].get("results") and 
                response_data["outputs"][0]["outputs"][0]["results"].get("message") and 
                response_data["outputs"][0]["outputs"][0]["results"]["message"].get("text")):
                
                message_text = response_data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
                
                # Return simplified response
                return {
                    "status": "success",
                    "message": message_text
                }
            else:
                # Return the full response if we couldn't extract the message
                return response_data
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return {
                "status": "error",
                "message": "Invalid JSON response from Langflow API",
                "details": response.text[:1000]  # First 1000 chars of the response
            }
            
    except requests.exceptions.Timeout:
        logger.error("Request to Langflow API timed out after 180 seconds")
        return {
            "status": "error",
            "message": "Request timed out after 180 seconds. The Langflow API is taking too long to respond."
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
            "message": f"Unexpected error: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))  # Use PORT from environment or default to 8080
    uvicorn.run(app, host="0.0.0.0", port=port)