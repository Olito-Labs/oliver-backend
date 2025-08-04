from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.supabase_client import supabase
from app.auth import get_current_user

router = APIRouter(prefix="/api/studies", tags=["studies"])

# Request/Response models
class CreateStudyRequest(BaseModel):
    title: str
    workflow_type: str
    description: Optional[str] = None

class UpdateStudyRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    current_step: Optional[int] = None
    workflow_status: Optional[str] = None
    workflow_data: Optional[Dict[str, Any]] = None

class StudyResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str]
    workflow_type: Optional[str]
    current_step: int
    workflow_status: str
    workflow_data: Dict[str, Any]
    created_at: str
    updated_at: str

@router.post("/", response_model=Dict[str, StudyResponse])
async def create_study(
    request: CreateStudyRequest,
    user=Depends(get_current_user)
):
    """Create a new study with workflow type"""
    try:
        study_id = str(uuid.uuid4())
        
        study_data = {
            'id': study_id,
            'user_id': user['uid'],
            'title': request.title,
            'description': request.description,
            'workflow_type': request.workflow_type,
            'current_step': 0,
            'workflow_status': 'not_started',
            'workflow_data': {},
            'intent': request.workflow_type or 'GENERAL'
        }
        
        result = supabase.table('studies').insert(study_data).execute()
        
        if result.data:
            return {"study": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create study")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating study: {str(e)}")

@router.get("/", response_model=Dict[str, List[StudyResponse]])
async def get_user_studies(user=Depends(get_current_user)):
    """Get all studies for the current user"""
    try:
        result = supabase.table('studies')\
            .select("*")\
            .eq('user_id', user['uid'])\
            .order('created_at', desc=True)\
            .execute()
            
        return {"studies": result.data or []}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching studies: {str(e)}")

@router.get("/{study_id}", response_model=Dict[str, StudyResponse])
async def get_study(study_id: str, user=Depends(get_current_user)):
    """Get a specific study"""
    try:
        result = supabase.table('studies')\
            .select("*")\
            .eq('id', study_id)\
            .eq('user_id', user['uid'])\
            .single()\
            .execute()
            
        if not result.data:
            raise HTTPException(status_code=404, detail="Study not found")
            
        return {"study": result.data}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Study not found")
        raise HTTPException(status_code=500, detail=f"Error fetching study: {str(e)}")

@router.patch("/{study_id}", response_model=Dict[str, StudyResponse])
async def update_study(
    study_id: str,
    request: UpdateStudyRequest,
    user=Depends(get_current_user)
):
    """Update study workflow state"""
    try:
        # Build update data
        update_data = {}
        if request.title is not None:
            update_data['title'] = request.title
        if request.description is not None:
            update_data['description'] = request.description
        if request.current_step is not None:
            update_data['current_step'] = request.current_step
        if request.workflow_status is not None:
            update_data['workflow_status'] = request.workflow_status
        if request.workflow_data is not None:
            update_data['workflow_data'] = request.workflow_data
            
        if not update_data:
            raise HTTPException(status_code=400, detail="No updates provided")
            
        result = supabase.table('studies')\
            .update(update_data)\
            .eq('id', study_id)\
            .eq('user_id', user['uid'])\
            .execute()
            
        if not result.data:
            raise HTTPException(status_code=404, detail="Study not found")
            
        return {"study": result.data[0]}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Study not found")
        raise HTTPException(status_code=500, detail=f"Error updating study: {str(e)}")

@router.delete("/{study_id}")
async def delete_study(study_id: str, user=Depends(get_current_user)):
    """Delete a study (soft delete by setting status to 'deleted')"""
    try:
        result = supabase.table('studies')\
            .update({'status': 'deleted'})\
            .eq('id', study_id)\
            .eq('user_id', user['uid'])\
            .execute()
            
        if not result.data:
            raise HTTPException(status_code=404, detail="Study not found")
            
        return {"message": "Study deleted successfully"}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Study not found")
        raise HTTPException(status_code=500, detail=f"Error deleting study: {str(e)}")