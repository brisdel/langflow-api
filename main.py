from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

class QueryRequest(BaseModel):
    message: str

def generate_simulated_response(message: str):
    # Log the incoming message
    logger.info(f"Generating simulated response for message: {message}")
    
    # Convert message to lowercase for easier keyword matching
    message_lower = message.lower()
    
    # Default response structure
    response = {
        "part_data": [],
        "contract_terms": [],
        "negotiation_insights": []
    }
    
    # Add simulated data based on keywords
    if "price" in message_lower or "cost" in message_lower:
        response["part_data"].append({
            "part_name": "Sample Part",
            "current_price": "$100",
            "suggested_price": "$90",
            "market_rate": "$95"
        })
        response["negotiation_insights"].append("Consider bulk ordering to reduce per-unit cost")
    
    if "delivery" in message_lower or "shipping" in message_lower:
        response["contract_terms"].append({
            "term": "Delivery Timeline",
            "current": "30 days",
            "suggested": "25 days"
        })
        response["negotiation_insights"].append("Express shipping options available at premium rates")
    
    if "quality" in message_lower:
        response["contract_terms"].append({
            "term": "Quality Assurance",
            "current": "Standard QA",
            "suggested": "Enhanced QA Process"
        })
    
    # Always include some general insights if no specific keywords matched
    if not any(response.values()):
        response["negotiation_insights"].append("Consider opening with your target price")
        response["negotiation_insights"].append("Focus on value-based negotiation")
    
    return response

@app.get("/")
def root():
    return {"message": "Negotiation API is running - Using simulated responses"}

@app.post("/query")
async def query(request: QueryRequest):
    try:
        logger.info(f"Received query request with message: {request.message}")
        
        # Generate simulated response
        response = generate_simulated_response(request.message)
        
        logger.info(f"Generated response: {json.dumps(response, indent=2)}")
        return {"status": "success", "data": response}
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)