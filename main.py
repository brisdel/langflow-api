from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json
import os
import time

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

class MessageRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {
        "message": "API is alive",
        "status": "healthy",
        "notice": "This API is currently using simulated responses while we address issues with the Langflow API."
    }

@app.post("/query")
async def query_agent(request: MessageRequest):
    logger.info(f"Query endpoint called with message: {request.message}")
    
    # Simulate processing time
    time.sleep(1)
    
    # Generate a simulated response based on the input
    if "negotiation" in request.message.lower():
        response_text = generate_negotiation_response(request.message)
    elif "price" in request.message.lower() or "cost" in request.message.lower():
        response_text = generate_pricing_response(request.message)
    elif "contract" in request.message.lower() or "agreement" in request.message.lower():
        response_text = generate_contract_response(request.message)
    else:
        response_text = generate_general_response(request.message)
    
    return {
        "status": "success",
        "message": response_text
    }

def generate_negotiation_response(message):
    return """### Negotiation Strategy Recommendations

1. **Opening Position**: Start with a stronger position than your target outcome
   - Initial offer: 15-20% below market rate
   - Highlight unique value propositions

2. **Concession Strategy**:
   - Make decreasing concessions (larger first, smaller later)
   - Always ask for something in return for each concession
   - Use silence strategically after counteroffers

3. **Key Talking Points**:
   - Industry benchmarks support our position
   - Our quality metrics exceed industry standards
   - We're offering flexible implementation timeline

4. **BATNA (Best Alternative To Negotiated Agreement)**:
   - Three other qualified vendors are ready to engage
   - Internal solution could be developed if necessary
   - Option to phase implementation to reduce initial commitment

Remember to listen actively and identify the other party's priorities to find creative win-win solutions."""

def generate_pricing_response(message):
    return """### Pricing Strategy Analysis

**Current Market Positioning**:
- Our price point is currently at the 65th percentile for comparable solutions
- Premium positioning is justified by additional service components

**Competitor Analysis**:
| Competitor | Base Price | Feature Set | Support | Market Share |
|------------|------------|-------------|---------|--------------|
| Alpha Inc. | $12,500    | Basic       | 9-5     | 28%          |
| Beta Corp. | $15,800    | Standard    | 24/7    | 31%          |
| Our Company| $17,200    | Premium     | 24/7    | 22%          |

**Recommended Approach**:
1. Emphasize total cost of ownership rather than upfront price
2. Highlight ROI timeline (typically 14 months to break even)
3. Offer tiered pricing structure with clear upgrade path
4. Consider volume discounts for multi-year commitments"""

def generate_contract_response(message):
    return """### Contract Terms Guidance

**Key Terms to Negotiate**:
1. **Payment Terms**: Net-45 with 2% discount for early payment
2. **Service Level Agreement**: 99.8% uptime with penalty clauses
3. **Liability Cap**: Limit to 12 months of fees paid
4. **IP Ownership**: All custom development should be client-owned
5. **Exit Provisions**: 90-day notice period with transition assistance

**Red Flags to Watch For**:
- Indemnification clauses that are overly broad
- Auto-renewal terms longer than 12 months
- Dispute resolution that specifies foreign jurisdictions
- One-sided termination rights

**Recommended Approvals Process**:
1. Legal review (2-3 business days)
2. Risk assessment (1 business day)
3. Executive sponsor sign-off (1 business day)"""

def generate_general_response(message):
    return f"""I've analyzed your message: "{message}"

### General Recommendations

1. **Clarify Objectives**: 
   - Define what success looks like for this negotiation
   - Prioritize your must-haves vs. nice-to-haves

2. **Research Preparation**:
   - Gather market intelligence on standard terms
   - Understand the other party's constraints and motivations
   - Prepare supporting data for your position

3. **Communication Strategy**:
   - Focus on interests rather than positions
   - Use open-ended questions to gather information
   - Frame proposals in terms of mutual benefit

4. **Next Steps**:
   - Develop a detailed negotiation plan with fallback positions
   - Prepare responses to likely objections
   - Consider role-playing difficult scenarios before the meeting

Would you like more specific guidance on any particular aspect of your negotiation?"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)