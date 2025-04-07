# main.py

from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os

app = FastAPI()

# Constants
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "ed6c45f6-6029-47a5-a6ee-86d7caf24d60"
FLOW_ID = "c4369450-5685-4bb4-85b3-f47b7dd0e917"

# Request body model
class QueryRequest(BaseModel):
    message: str

# Health check route
@app.get("/")
def root():
    return {"message": "API is alive"}

# Langflow query route
@app.post("/query")
def query_agent(request: QueryRequest):
    # Dynamically load the token
    application_token = os.getenv("APPLICATION_TOKEN")

    if not application_token:
        return {
            "status": "error",
            "message": "APPLICATION_TOKEN is not set in environment variables."
        }

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
        response = requests.post(api_url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Langflow request failed: {str(e)}"
        }
