# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
import requests
import os
import json

app = FastAPI()

BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "ed6c45f6-6029-47a5-a6ee-86d7caf24d60"
FLOW_ID = "c4369450-5685-4bb4-85b3-f47b7dd0e917"
APPLICATION_TOKEN = os.getenv("APPLICATION_TOKEN")

class QueryRequest(BaseModel):
    message: str
@app.get("/")
def root():
    return {"message": "API is alive"}

@app.post("/query")
def query_agent(request: QueryRequest):
    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{FLOW_ID}"
    headers = {
        "Authorization": f"Bearer {APPLICATION_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "input_value": request.message,
        "output_type": "chat",
        "input_type": "chat"
    }

    response = requests.post(api_url, json=payload, headers=headers)

    try:
        return response.json()
    except:
        return {"error": "Failed to parse Langflow response"}
