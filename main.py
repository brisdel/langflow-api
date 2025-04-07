from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
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

class LangflowRequest(BaseModel):
    input_value: str
    output_type: str = "chat"
    input_type: str = "chat"
    tweaks: Dict[str, Any] = {
        "Agent-cfbu4": {},
        "ChatInput-URWrQ": {},
        "ChatOutput-8jfCH": {},
        "AstraDBToolComponent-HX1wm": {},
        "AstraDB-1zteC": {},
        "ParseDataFrame-uutq1": {}
    }

@app.get("/")
async def root():
    return {"message": "API is alive"}

@app.post("/query")
async def query_agent(request: LangflowRequest):
    logger.info(f"Query endpoint called with input: {request.input_value}")
    
    application_token = os.getenv("APPLICATION_TOKEN")
    if not application_token:
        logger.error("APPLICATION_TOKEN not found")
        return {
            "status": "error",
            "message": "APPLICATION_TOKEN is not set"
        }

    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    headers = {
        "Authorization": f"Bearer {application_token}",
        "Content-Type": "application/json"
    }
    
    # Use the request model directly as the payload
    payload = request.dict()

    try:
        logger.info(f"Sending request to: {api_url}")
        logger.info(f"With payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(api_url, json=payload, headers=headers)
        
        # Log response details
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        logger.info(f"Response content: {response.text}")
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Langflow API returned status {response.status_code}",
                "details": response.text
            }
            
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Request failed: {str(e)}",
            "details": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "details": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)