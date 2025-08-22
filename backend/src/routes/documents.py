from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Dict, Optional
import os
import uuid
import tempfile
import json
import logging
from datetime import datetime

from src.core.database import get_db
from src.core.security import get_current_user
from src.core.cache import cache_service
from src.core.websocket_manager import websocket_manager
from src.services.document_service import document_processor
from src.models.models import User, Document, Quote
from src.core.settings import settings

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_document(
    files: List[UploadFile] = File(...),
    quote_id: Optional[int] = Form(None),
    processing_options: Optional[str] = Form("{}"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload single or multiple documents for processing"""
    
    try:
        # Validate file count
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")
        
        # Parse processing options
        try:
            options = json.loads(processing_options)
        except json.JSONDecodeError:
            options = {}
        
        # Validate quote ownership if specified
        if quote_id:
            result = await db.execute(
                select(Quote).where(
                    and_(Quote.id == quote_id, Quote.user_id == current_user.id)
                )
            )
            quote = result.scalar_one_or_none()
            if not quote:
                raise HTTPException(status_code=404, detail="Quote not found or access denied")
        
        uploaded_files = []
        temp_files = []
        batch_id = str(uuid.uuid4())
        
        try:
            # Process each uploaded file
            for file in files:
                # Validate file
                if not file.filename:
                    continue
                
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_files.append(temp_file.name)
                
                # Save uploaded file
                content = await file.read()
                temp_file.write(content)
                temp_file.close()
                
                # Validate file
                validation = document_processor.validate_file(
                    temp_file.name, 
                    file.filename,
                    max_size_mb=settings.max_file_size // (1024 * 1024)
                )
                
                if not validation["valid"]:
                    raise HTTPException(status_code=400, detail=f"File {file.filename}: {validation['error']}")
                
                # Create permanent file path
                upload_dir = os.path.join(settings.upload_dir, "documents", str(current_user.id))
                os.makedirs(upload_dir, exist_ok=True)
                
                file_uuid = str(uuid.uuid4())
                file_ext = os.path.splitext(file.filename)[1]
                permanent_path = os.path.join(upload_dir, f"{file_uuid}{file_ext}")
                
                # Move file to permanent location
                os.rename(temp_file.name, permanent_path)
                temp_files.remove(temp_file.name)  # Remove from cleanup list
                
                # Create database record
                document = Document(
                    user_id=current_user.id,
                    quote_id=quote_id,
                    batch_id=batch_id,
                    filename=f"{file_uuid}{file_ext}",
                    original_filename=file.filename,
                    file_path=permanent_path,
                    file_size=validation["file_size"],
                    mime_type=file.content_type or "application/octet-stream",
                    processing_status="uploaded"
                )
                
                db.add(document)
                await db.flush()  # Get the document ID
                
                uploaded_files.append({
                    "document_id": document.id,
                    "filename": file.filename,
                    "file_path": permanent_path,
                    "content_type": file.content_type
                })
            
            await db.commit()
            
            # Start background processing
            if uploaded_files:
                await start_batch_processing(uploaded_files, current_user.id, options)
            
            return {
                "success": True,
                "message": f"Successfully uploaded {len(uploaded_files)} documents",
                "batch_id": batch_id,
                "documents": [
                    {
                        "document_id": doc["document_id"],
                        "filename": doc["filename"]
                    } for doc in uploaded_files
                ],
                "processing_started": True
            }
            
        except Exception as e:
            # Cleanup temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            # Cleanup uploaded files on error
            for uploaded_file in uploaded_files:
                try:
                    os.unlink(uploaded_file["file_path"])
                except:
                    pass
            
            await db.rollback()
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Upload failed")

async def start_batch_processing(uploaded_files: List[Dict], user_id: int, options: Dict):
    """Start background batch processing of uploaded documents"""
    
    try:
        # Prepare data for batch processing
        file_paths = [doc["file_path"] for doc in uploaded_files]
        filenames = [doc["filename"] for doc in uploaded_files]
        content_types = [doc["content_type"] for doc in uploaded_files]
        
        # Send processing start notification
        await websocket_manager.send_to_user({
            "type": "document_processing_started",
            "message": f"Processing {len(uploaded_files)} documents...",
            "document_count": len(uploaded_files)
        }, user_id)
        
        # Process documents
        results = await document_processor.process_batch(
            file_paths, filenames, content_types, user_id, options
        )
        
        # Update database with results
        from src.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            for i, (uploaded_file, result) in enumerate(zip(uploaded_files, results)):
                document_id = uploaded_file["document_id"]
                
                # Get document
                doc_result = await db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                if document:
                    # Update document with processing results
                    document.processing_status = "completed" if result.get("success", True) else "failed"
                    document.extracted_text = result.get("extracted_text", "")
                    document.text_confidence = result.get("text_confidence", 0.0)
                    document.handwriting_detected = result.get("handwriting_detected", False)
                    document.processing_method = result.get("processing_method", "")
                    document.analysis_result = json.dumps(result, ensure_ascii=False)
                    document.page_count = len(result.get("pages", []))
                    
                    # Extract structured data
                    if result.get("pages"):
                        # Try to detect rooms and measurements
                        text = result.get("extracted_text", "").lower()
                        rooms = extract_room_info(text)
                        measurements = extract_measurements(text)
                        
                        document.detected_rooms = json.dumps(rooms) if rooms else None
                        document.detected_measurements = json.dumps(measurements) if measurements else None
                    
                    # Store table data
                    if result.get("tables"):
                        document.detected_tables = json.dumps(result["tables"], ensure_ascii=False)
                    
                    await db.commit()
        
        # Send completion notification
        await websocket_manager.send_to_user({
            "type": "document_processing_completed",
            "message": "Document processing completed",
            "results": results
        }, user_id)
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        
        # Send error notification
        await websocket_manager.send_to_user({
            "type": "document_processing_error",
            "message": f"Document processing failed: {str(e)}"
        }, user_id)

def extract_room_info(text: str) -> List[str]:
    """Extract room information from text"""
    
    room_keywords = [
        'wohnzimmer', 'schlafzimmer', 'küche', 'badezimmer', 'bad', 'wc',
        'kinderzimmer', 'arbeitszimmer', 'büro', 'flur', 'diele', 'keller',
        'dachboden', 'garage', 'balkon', 'terrasse', 'garten', 'zimmer'
    ]
    
    found_rooms = []
    for keyword in room_keywords:
        if keyword in text:
            # Try to find context around the keyword
            import re
            pattern = rf'\b\w*{keyword}\w*\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            found_rooms.extend(matches)
    
    return list(set(found_rooms))

def extract_measurements(text: str) -> List[Dict]:
    """Extract measurements from text"""
    
    import re
    
    measurements = []
    
    # Pattern for measurements: number + unit
    patterns = [
        r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(m²|qm|quadratmeter)',
        r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(m|meter)',
        r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(cm|zentimeter)',
        r'(\d+(?:,\d+)?(?:\.\d+)?)\s*x\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(m|cm)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) == 2:  # value + unit
                measurements.append({
                    "value": match[0].replace(',', '.'),
                    "unit": match[1].lower(),
                    "type": "measurement"
                })
            elif len(match) == 3:  # width x height + unit
                measurements.append({
                    "width": match[0].replace(',', '.'),
                    "height": match[1].replace(',', '.'),
                    "unit": match[2].lower(),
                    "type": "dimensions"
                })
    
    return measurements

@router.get("/list")
async def list_documents(
    quote_id: Optional[int] = None,
    batch_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's documents with optional filtering"""
    
    try:
        # Build query
        query = select(Document).where(Document.user_id == current_user.id)
        
        if quote_id:
            query = query.where(Document.quote_id == quote_id)
        
        if batch_id:
            query = query.where(Document.batch_id == batch_id)
        
        query = query.order_by(Document.created_at.desc())
        
        result = await db.execute(query)
        documents = result.scalars().all()
        
        # Format response
        document_list = []
        for doc in documents:
            document_data = {
                "id": doc.id,
                "filename": doc.original_filename,
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "processing_status": doc.processing_status,
                "text_confidence": doc.text_confidence,
                "handwriting_detected": doc.handwriting_detected,
                "page_count": doc.page_count,
                "created_at": doc.created_at.isoformat(),
                "quote_id": doc.quote_id,
                "batch_id": doc.batch_id
            }
            
            # Include extracted data if processing completed
            if doc.processing_status == "completed":
                document_data.update({
                    "has_text": bool(doc.extracted_text),
                    "has_tables": bool(doc.detected_tables),
                    "detected_rooms": json.loads(doc.detected_rooms) if doc.detected_rooms else [],
                    "detected_measurements": json.loads(doc.detected_measurements) if doc.detected_measurements else []
                })
            
            document_list.append(document_data)
        
        return {
            "success": True,
            "documents": document_list,
            "total": len(document_list)
        }
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")

@router.get("/{document_id}")
async def get_document_details(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed document information and analysis results"""
    
    try:
        # Get document
        result = await db.execute(
            select(Document).where(
                and_(Document.id == document_id, Document.user_id == current_user.id)
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Build response
        response = {
            "id": document.id,
            "filename": document.original_filename,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            "processing_status": document.processing_status,
            "processing_method": document.processing_method,
            "text_confidence": document.text_confidence,
            "handwriting_detected": document.handwriting_detected,
            "page_count": document.page_count,
            "created_at": document.created_at.isoformat(),
            "quote_id": document.quote_id,
            "batch_id": document.batch_id
        }
        
        # Include processing results if completed
        if document.processing_status == "completed":
            response.update({
                "extracted_text": document.extracted_text,
                "detected_rooms": json.loads(document.detected_rooms) if document.detected_rooms else [],
                "detected_measurements": json.loads(document.detected_measurements) if document.detected_measurements else [],
                "detected_tables": json.loads(document.detected_tables) if document.detected_tables else []
            })
            
            # Include full analysis result if requested
            if document.analysis_result:
                try:
                    response["full_analysis"] = json.loads(document.analysis_result)
                except:
                    pass
        
        return {"success": True, "document": response}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get document details")

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a document"""
    
    try:
        # Get document
        result = await db.execute(
            select(Document).where(
                and_(Document.id == document_id, Document.user_id == current_user.id)
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete physical file
        try:
            if os.path.exists(document.file_path):
                os.unlink(document.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete physical file: {e}")
        
        # Delete database record
        await db.delete(document)
        await db.commit()
        
        return {"success": True, "message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete document")

@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    processing_options: Dict = {},
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reprocess a document with different options"""
    
    try:
        # Get document
        result = await db.execute(
            select(Document).where(
                and_(Document.id == document_id, Document.user_id == current_user.id)
            )
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not os.path.exists(document.file_path):
            raise HTTPException(status_code=404, detail="Document file not found")
        
        # Update status
        document.processing_status = "processing"
        await db.commit()
        
        # Send notification
        await websocket_manager.send_to_user({
            "type": "document_reprocessing_started",
            "document_id": document_id,
            "message": "Reprocessing document..."
        }, current_user.id)
        
        # Reprocess document
        result = await document_processor.process_document(
            document.file_path,
            document.original_filename,
            document.mime_type,
            current_user.id,
            processing_options
        )
        
        # Update database with new results
        if result.get("success", True):
            document.processing_status = "completed"
            document.extracted_text = result.get("extracted_text", "")
            document.text_confidence = result.get("text_confidence", 0.0)
            document.handwriting_detected = result.get("handwriting_detected", False)
            document.processing_method = result.get("processing_method", "")
            document.analysis_result = json.dumps(result, ensure_ascii=False)
            document.page_count = len(result.get("pages", []))
            
            # Update structured data
            if result.get("extracted_text"):
                text = result["extracted_text"].lower()
                rooms = extract_room_info(text)
                measurements = extract_measurements(text)
                
                document.detected_rooms = json.dumps(rooms) if rooms else None
                document.detected_measurements = json.dumps(measurements) if measurements else None
            
            if result.get("tables"):
                document.detected_tables = json.dumps(result["tables"], ensure_ascii=False)
        else:
            document.processing_status = "failed"
        
        await db.commit()
        
        # Send completion notification
        await websocket_manager.send_to_user({
            "type": "document_reprocessing_completed",
            "document_id": document_id,
            "success": result.get("success", True),
            "message": "Document reprocessing completed"
        }, current_user.id)
        
        return {
            "success": True,
            "message": "Document reprocessed successfully",
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing document: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reprocess document")

@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get processing status of a document batch"""
    
    try:
        # Get documents in batch
        result = await db.execute(
            select(Document).where(
                and_(Document.batch_id == batch_id, Document.user_id == current_user.id)
            )
        )
        documents = result.scalars().all()
        
        if not documents:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Calculate status
        total = len(documents)
        completed = sum(1 for doc in documents if doc.processing_status == "completed")
        failed = sum(1 for doc in documents if doc.processing_status == "failed")
        processing = sum(1 for doc in documents if doc.processing_status == "processing")
        
        return {
            "success": True,
            "batch_id": batch_id,
            "total_documents": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "pending": total - completed - failed - processing,
            "progress_percentage": (completed / total * 100) if total > 0 else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get batch status")