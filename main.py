from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List
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

class LangflowRequest(BaseModel):
    message: str = Field(..., description="The input message for the flow")

@app.get("/")
async def root():
    return {
        "message": "API is alive",
        "status": "healthy"
    }

@app.post("/query")
async def query_agent(request: LangflowRequest):
    logger.info(f"Query endpoint called with message: {request.message}")
    
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
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Simplified payload structure
    payload = {
        "input_value": request.message,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": TWEAKS
    }

    try:
        logger.info(f"Sending request to: {api_url}")
        logger.info(f"With payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(api_url, json=payload, headers=headers)
        
        # Log complete response information
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        logger.info(f"Response content: {response.text[:1000]}")  # First 1000 chars

        # If response status is not 200, return error
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Langflow API returned status {response.status_code}",
                "details": response.text
            }

        # Try to parse JSON response
        try:
            return response.json()
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": "Failed to parse Langflow API response",
                "details": {
                    "error": str(e),
                    "response_text": response.text[:1000]  # First 1000 chars
                }
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to connect to Langflow API: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)