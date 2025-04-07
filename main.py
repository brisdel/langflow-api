from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import logging
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
    logger.info("Query endpoint called")
    
    # Dynamically load the token
    application_token = os.getenv("APPLICATION_TOKEN")

    if not application_token:
        logger.error("APPLICATION_TOKEN not found")
        raise HTTPException(
            status_code=500,
            detail="APPLICATION_TOKEN is not set in environment variables."
        )

    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    headers = {
        "Authorization": f"Bearer {application_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "input_value": request.message,
        "output_type": "chat",
        "input_type": "chat"
    }

    try:
        logger.info(f"Sending request to Langflow API: {api_url}")
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Langflow request failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Langflow request failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)