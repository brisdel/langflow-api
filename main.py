from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json
import requests
import os

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
    "Agent-dlR1n": {},
    "ChatInput-cnDzP": {},
    "ChatOutput-Ffc1R": {},
    "AstraDBToolComponent-OkQEv": {}
}

class QueryRequest(BaseModel):
    message: str

def call_langflow_api(message: str, application_token: str) -> dict:
    """
    Call the Langflow API with error handling and logging
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
    
    try:
        logger.info(f"Calling Langflow API at: {api_url}")
        logger.info(f"With payload: {json.dumps(payload, indent=2)}")
        logger.info(f"Authorization header starts with: {headers['Authorization'][:15]}...")  # Log first part of auth header safely
        
        # Using a 60-second timeout for the simpler flow
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        
        try:
            response_text = response.text
            logger.info(f"Response text: {response_text[:1000]}")  # Log first 1000 chars
        except Exception as e:
            logger.error(f"Could not read response text: {str(e)}")
        
        if response.status_code != 200:
            error_msg = f"Langflow API returned status {response.status_code}"
            try:
                error_detail = response.json()
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
        logger.error("Request to Langflow API timed out after 60 seconds")
        raise HTTPException(
            status_code=504,
            detail="Request timed out after 60 seconds. The Langflow API is taking too long to respond."
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
    """Health check endpoint that also verifies environment variables"""
    application_token = os.getenv("APPLICATION_TOKEN")
    return {
        "status": "healthy",
        "message": "API is alive",
        "environment": {
            "port": os.getenv("PORT"),
            "has_token": bool(application_token),
            "token_length": len(application_token) if application_token else 0
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