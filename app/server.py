from dotenv import load_dotenv
load_dotenv()  # Load environment variables before importing other modules

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any

from main import run_once
from orchestration.types import RealEstateRequest

app = FastAPI(title="Real Estate Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    address: str
    asset_class: str = "residential"
    mls_id: str

class AnalysisResponse(BaseModel):
    success: bool
    data: Dict[str, Any] = None
    error: Dict[str, Any] = None

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_property(request: AnalysisRequest):
    try:
        # Run the orchestration workflow
        result = run_once(
            address=request.address,
            asset_class=request.asset_class,
            mls_id=request.mls_id
        )
        
        return AnalysisResponse(
            success=True,
            data=result
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Analysis failed: {str(e)}",
                "code": "ANALYSIS_ERROR"
            }
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)