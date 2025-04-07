from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "ed6c45f6-6029-47a5-a6ee-86d7caf24d60"
FLOW_ID = "c4369450-5685-4bb4-85b3-f47b7dd0e917"

DEFAULT_TWEAKS = {
    "Agent-cfbu4": {},
    "ChatInput-URWrQ": {},
    "ChatOutput-8jfCH": {},
    "AstraDBToolComponent-HX1wm": {},
    "AstraDB-1zteC": {},
    "ParseDataFrame-uutq1": {}
}

class LangflowRequest(BaseModel):
    input_value: str = Field(..., description="The input message for the flow")
    output_type: str = Field(default="chat", description="The type of output expected")
    input_type: str = Field(default="chat", description="The type of input being sent")
    tweaks: Dict[str, Dict] = Field(default=DEFAULT_TWEAKS, description="Flow-specific tweaks")

    class Config:
        schema_extra = {
            "example": {
                "input_value": "Hello",
                "output_type": "chat",
                "input_type": "chat",
                "tweaks": DEFAULT_TWEAKS
            }
        }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "type": str(type(exc).__name__)}
    )

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

@app.get("/")
async def root():
    logger.info("Health check endpoint called")
    return {
        "status": "healthy",
        "message": "API is alive",
        "environment": {
            "port": os.getenv("PORT"),
            "has_token": bool(os.getenv("APPLICATION_TOKEN"))
        },
        "example_request": LangflowRequest.Config.schema_extra["example"]
    }

@app.post("/query")
async def query_agent(request: LangflowRequest):
    logger.info(f"Query endpoint called with input: {request.input_value}")
    logger.info(f"Full request: {request.dict()}")
    
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
    port = int(os.getenv("PORT", 8080))  # Use PORT from environment or default to 8080
    uvicorn.run(app, host="0.0.0.0", port=port)