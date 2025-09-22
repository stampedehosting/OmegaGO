#!/usr/bin/env python3
"""
FastAPI server for the Stampede Hosting provisioning pipeline
Provides REST API endpoints for triggering provisioning and checking status
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import json
import time
from provisioning_pipeline import ProvisioningPipeline, ProvisioningRequest, KitType, ProvisioningStatus

app = FastAPI(
    title="Stampede Hosting Provisioning API",
    description="Automated provisioning pipeline for hosting services",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for request status (in production, use a database)
provisioning_requests: Dict[str, Dict[str, Any]] = {}

# Initialize provisioning pipeline
pipeline = ProvisioningPipeline()

class ProvisioningRequestModel(BaseModel):
    """Pydantic model for provisioning requests"""
    kit_type: str
    customer_id: str
    domain_name: str
    github_repo: Optional[str] = None
    custom_config: Optional[Dict[str, Any]] = None

class ProvisioningResponseModel(BaseModel):
    """Pydantic model for provisioning responses"""
    request_id: str
    status: str
    message: str

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Stampede Hosting Provisioning API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": int(time.time())}

@app.get("/kits")
async def list_available_kits():
    """List all available kit types"""
    return {
        "kits": [
            {
                "id": "starter_site",
                "name": "Starter Site Kit",
                "description": "Quick and easy single-page website",
                "resources": "1 vCPU, 1GB RAM, 25GB SSD"
            },
            {
                "id": "course_launch",
                "name": "Course Launch Kit", 
                "description": "Complete online course platform",
                "resources": "2 vCPUs, 4GB RAM, 100GB SSD"
            },
            {
                "id": "developer_sandbox",
                "name": "Developer Sandbox Kit",
                "description": "Flexible development environment",
                "resources": "4 vCPUs, 8GB RAM, 200GB SSD"
            }
        ]
    }

@app.post("/provision", response_model=ProvisioningResponseModel)
async def create_provisioning_request(
    request: ProvisioningRequestModel,
    background_tasks: BackgroundTasks
):
    """Create a new provisioning request"""
    
    # Validate kit type
    try:
        kit_type = KitType(request.kit_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid kit type: {request.kit_type}")
    
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    
    # Create provisioning request object
    prov_request = ProvisioningRequest(
        kit_type=kit_type,
        customer_id=request.customer_id,
        domain_name=request.domain_name,
        github_repo=request.github_repo,
        custom_config=request.custom_config,
        request_id=request_id
    )
    
    # Store request status
    provisioning_requests[request_id] = {
        "request": prov_request.__dict__,
        "status": ProvisioningStatus.PENDING.value,
        "created_at": int(time.time()),
        "result": None
    }
    
    # Start provisioning in background
    background_tasks.add_task(run_provisioning, request_id, prov_request)
    
    return ProvisioningResponseModel(
        request_id=request_id,
        status=ProvisioningStatus.PENDING.value,
        message="Provisioning request created successfully"
    )

@app.get("/provision/{request_id}")
async def get_provisioning_status(request_id: str):
    """Get the status of a provisioning request"""
    
    if request_id not in provisioning_requests:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    
    request_data = provisioning_requests[request_id]
    
    return {
        "request_id": request_id,
        "status": request_data["status"],
        "created_at": request_data["created_at"],
        "result": request_data.get("result")
    }

@app.get("/provision")
async def list_provisioning_requests():
    """List all provisioning requests"""
    return {
        "requests": [
            {
                "request_id": req_id,
                "status": data["status"],
                "customer_id": data["request"]["customer_id"],
                "kit_type": data["request"]["kit_type"],
                "created_at": data["created_at"]
            }
            for req_id, data in provisioning_requests.items()
        ]
    }

@app.delete("/provision/{request_id}")
async def cancel_provisioning_request(request_id: str):
    """Cancel a provisioning request (if still pending)"""
    
    if request_id not in provisioning_requests:
        raise HTTPException(status_code=404, detail="Provisioning request not found")
    
    request_data = provisioning_requests[request_id]
    
    if request_data["status"] != ProvisioningStatus.PENDING.value:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel request with status: {request_data['status']}"
        )
    
    # Mark as cancelled
    provisioning_requests[request_id]["status"] = "cancelled"
    
    return {"message": "Provisioning request cancelled successfully"}

async def run_provisioning(request_id: str, prov_request: ProvisioningRequest):
    """Background task to run the provisioning pipeline"""
    
    try:
        # Update status to provisioning
        provisioning_requests[request_id]["status"] = ProvisioningStatus.PROVISIONING.value
        
        # Run the provisioning pipeline
        result = pipeline.provision_environment(prov_request)
        
        # Update request with result
        provisioning_requests[request_id]["status"] = result["status"]
        provisioning_requests[request_id]["result"] = result
        provisioning_requests[request_id]["completed_at"] = int(time.time())
        
    except Exception as e:
        # Handle provisioning errors
        provisioning_requests[request_id]["status"] = ProvisioningStatus.FAILED.value
        provisioning_requests[request_id]["result"] = {
            "error": str(e)
        }
        provisioning_requests[request_id]["completed_at"] = int(time.time())

@app.post("/webhook/github")
async def github_webhook(payload: Dict[str, Any]):
    """Handle GitHub webhooks for deployment triggers"""
    
    # Extract relevant information from GitHub webhook
    event_type = payload.get("action", "unknown")
    repository = payload.get("repository", {}).get("name", "unknown")
    
    # Log the webhook event
    print(f"GitHub webhook received: {event_type} for repository {repository}")
    
    # Here you could trigger redeployment or other actions
    # based on the webhook payload
    
    return {"message": "Webhook processed successfully"}

@app.post("/webhook/replit")
async def replit_webhook(payload: Dict[str, Any]):
    """Handle Replit webhooks for deployment status"""
    
    # Extract relevant information from Replit webhook
    event_type = payload.get("type", "unknown")
    project_id = payload.get("project_id", "unknown")
    
    # Log the webhook event
    print(f"Replit webhook received: {event_type} for project {project_id}")
    
    return {"message": "Webhook processed successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
