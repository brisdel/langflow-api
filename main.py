from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json
import requests
import os

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

# Constants for Langflow API
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

class QueryRequest(BaseModel):
    message: str

def call_langflow_api(message: str, application_token: str) -> dict:
    """
    Call the Langflow API with error handling and logging
    """
    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    
    headers = {
        "Authorization": f"Bearer {application_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "input_value": message,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": TWEAKS
    }
    
    try:
        logger.info(f"Sending request to Langflow API for message: {message}")
        response = requests.post(api_url, json=payload, headers=headers, timeout=180)  # 3 minute timeout
        
        logger.info(f"Received response from Langflow API with status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Langflow API error: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Langflow API returned status {response.status_code}: {response.text}"
            )
        
        response_data = response.json()
        
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
            logger.warning("Unexpected response structure from Langflow API")
            return {"status": "success", "data": response_data}  # Return full response if structure is different
            
    except requests.exceptions.Timeout:
        logger.error("Request to Langflow API timed out after 180 seconds")
        raise HTTPException(
            status_code=504,
            detail="Request timed out after 180 seconds. The Langflow API is taking too long to respond."
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

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "API is alive",
        "environment": {
            "port": os.getenv("PORT"),
            "has_token": bool(os.getenv("APPLICATION_TOKEN"))
        }
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
        
        # Call Langflow API
        response = call_langflow_api(request.message, application_token)
        
        logger.info("Successfully processed query")
        return response
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as they already have the right format
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