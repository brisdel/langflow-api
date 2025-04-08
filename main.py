from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

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

class QueryRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {
        "message": "API is alive",
        "status": "healthy"
    }

@app.post("/query")
async def query_agent(request: QueryRequest):
    logger.info(f"Query endpoint called with message: {request.message}")
    
    # Just return a simple static response
    return {
        "status": "success",
        "message": f"Received your message: {request.message}. Here is a simulated response for negotiation strategies."
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)