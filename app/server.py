from dotenv import load_dotenv
load_dotenv()  # Load environment variables before importing other modules

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

from main import run_once
from orchestration.types import RealEstateRequest
from database import episodic_db

app = FastAPI(title="Komps API", version="1.0.0")

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

class Partner(BaseModel):
    id: str
    name: str
    title: str
    email: str
    company: str

class EpisodicMemoryRequest(BaseModel):
    report_id: str
    property_address: str
    selected_partners: List[Partner]
    message: Optional[str] = None
    analyst: Dict[str, str]  # Contains id, name, title
    report_data: Dict[str, Any]

class EpisodicMemoryResponse(BaseModel):
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

@app.post("/api/episodic-memory", response_model=EpisodicMemoryResponse)
async def save_episodic_memory(request: EpisodicMemoryRequest):
    """Save report forwarding event as episodic memory."""
    try:
        # Create the episodic memory structure
        memory_data = {
            "event_type": "report_forwarded",
            "timestamp": datetime.utcnow().isoformat(),
            "analyst": request.analyst,
            "property_address": request.property_address,
            "report_id": request.report_id,
            "selected_partners": [partner.dict() for partner in request.selected_partners],
            "message": request.message,
            "context": {
                "forwarding_method": "manual_selection",
                "report_sections": list(request.report_data.get("sections", {}).keys()) if request.report_data else [],
                "estimated_value": request.report_data.get("valuation", {}).get("estimate") if request.report_data else None,
                "asset_class": request.report_data.get("subject", {}).get("assetClass") if request.report_data else None
            },
            "metadata": {
                "partners_count": len(request.selected_partners),
                "has_message": bool(request.message),
                "report_complete": bool(request.report_data)
            }
        }
        
        # Save to database
        memory_id = episodic_db.save_memory(memory_data)
        
        return EpisodicMemoryResponse(
            success=True,
            data={"memory_id": memory_id, "event_type": "report_forwarded"}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to save episodic memory: {str(e)}",
                "code": "MEMORY_SAVE_ERROR"
            }
        )

@app.get("/api/episodic-memory", response_model=EpisodicMemoryResponse)
async def get_episodic_memories(
    limit: Optional[int] = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
    analyst_id: Optional[str] = Query(None)
):
    """Retrieve episodic memories with optional filtering."""
    try:
        memories = episodic_db.get_memories(
            limit=limit,
            offset=offset,
            event_type=event_type,
            analyst_id=analyst_id
        )
        
        return EpisodicMemoryResponse(
            success=True,
            data={
                "memories": memories,
                "count": len(memories),
                "limit": limit,
                "offset": offset
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to retrieve episodic memories: {str(e)}",
                "code": "MEMORY_RETRIEVAL_ERROR"
            }
        )

@app.get("/api/episodic-memory/stats", response_model=EpisodicMemoryResponse)
async def get_memory_stats():
    """Get statistics about stored episodic memories."""
    try:
        stats = episodic_db.get_memory_stats()
        
        return EpisodicMemoryResponse(
            success=True,
            data=stats
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to get memory statistics: {str(e)}",
                "code": "MEMORY_STATS_ERROR"
            }
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)