import pytest
import io
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from src.models.models import User

class TestDocumentsIntegration:
    """Integration tests for documents endpoints"""

    async def test_upload_document(self, client: AsyncClient, auth_headers: dict):
        """Test document upload"""
        # Create a fake file
        file_content = b"This is a test document content"
        files = {"file": ("test_document.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {
            "title": "Test Document",
            "description": "A test document for integration testing"
        }
        
        response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        assert response.status_code == 201
        
        response_data = response.json()
        assert response_data["title"] == "Test Document"
        assert response_data["description"] == "A test document for integration testing"
        assert response_data["filename"] == "test_document.pdf"
        assert response_data["file_type"] == "application/pdf"
        assert "id" in response_data
        assert "upload_path" in response_data

    async def test_upload_document_unauthorized(self, client: AsyncClient):
        """Test document upload without authentication"""
        file_content = b"Test content"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        
        response = await client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 401

    async def test_upload_invalid_file_type(self, client: AsyncClient, auth_headers: dict):
        """Test uploading invalid file type"""
        file_content = b"Fake executable content"
        files = {"file": ("malicious.exe", io.BytesIO(file_content), "application/x-executable")}
        
        response = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        assert response.status_code == 400
        assert "file type not allowed" in response.json()["detail"].lower()

    async def test_upload_oversized_file(self, client: AsyncClient, auth_headers: dict):
        """Test uploading file that exceeds size limit"""
        # Create a large file (assuming 10MB limit from settings)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")}
        
        response = await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
        assert response.status_code == 413

    async def test_get_user_documents(self, client: AsyncClient, auth_headers: dict):
        """Test getting user's documents"""
        # First upload a document
        file_content = b"Test document for listing"
        files = {"file": ("list_test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "List Test Document"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        assert upload_response.status_code == 201
        
        # Get documents list
        response = await client.get("/api/v1/documents/", headers=auth_headers)
        assert response.status_code == 200
        
        documents = response.json()
        assert isinstance(documents, list)
        assert len(documents) >= 1
        
        # Find our uploaded document
        uploaded_doc = next((doc for doc in documents if doc["title"] == "List Test Document"), None)
        assert uploaded_doc is not None
        assert uploaded_doc["filename"] == "list_test.pdf"

    async def test_get_document_by_id(self, client: AsyncClient, auth_headers: dict):
        """Test getting specific document by ID"""
        # Upload a document first
        file_content = b"Document for ID test"
        files = {"file": ("id_test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "ID Test Document"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Get document by ID
        response = await client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert response.status_code == 200
        
        document = response.json()
        assert document["id"] == document_id
        assert document["title"] == "ID Test Document"

    async def test_get_nonexistent_document(self, client: AsyncClient, auth_headers: dict):
        """Test getting nonexistent document"""
        response = await client.get("/api/v1/documents/99999", headers=auth_headers)
        assert response.status_code == 404

    async def test_download_document(self, client: AsyncClient, auth_headers: dict):
        """Test downloading a document"""
        # Upload a document first
        original_content = b"Content for download test"
        files = {"file": ("download_test.pdf", io.BytesIO(original_content), "application/pdf")}
        data = {"title": "Download Test"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Download the document
        response = await client.get(f"/api/v1/documents/{document_id}/download", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")

    async def test_update_document_metadata(self, client: AsyncClient, auth_headers: dict):
        """Test updating document metadata"""
        # Upload a document first
        file_content = b"Document for update test"
        files = {"file": ("update_test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "Original Title"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Update metadata
        update_data = {
            "title": "Updated Title",
            "description": "Updated description for the document"
        }
        
        response = await client.put(f"/api/v1/documents/{document_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        
        updated_doc = response.json()
        assert updated_doc["title"] == "Updated Title"
        assert updated_doc["description"] == "Updated description for the document"

    async def test_delete_document(self, client: AsyncClient, auth_headers: dict):
        """Test deleting a document"""
        # Upload a document first
        file_content = b"Document for deletion test"
        files = {"file": ("delete_test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "Document to Delete"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Delete the document
        response = await client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = await client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert get_response.status_code == 404

    @patch('src.services.document_service.DocumentService.extract_text')
    async def test_extract_text_from_document(self, mock_extract, client: AsyncClient, auth_headers: dict):
        """Test text extraction from document"""
        mock_extract.return_value = {
            "extracted_text": "This is the extracted text from the document",
            "page_count": 1,
            "word_count": 10,
            "extraction_confidence": 0.95
        }
        
        # Upload a document first
        file_content = b"PDF content for text extraction"
        files = {"file": ("text_extract.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "Text Extraction Test"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Extract text
        response = await client.post(f"/api/v1/documents/{document_id}/extract-text", headers=auth_headers)
        assert response.status_code == 200
        
        extraction_result = response.json()
        assert "extracted_text" in extraction_result
        assert "page_count" in extraction_result
        assert extraction_result["word_count"] == 10

    @patch('src.services.document_service.DocumentService.analyze_floor_plan')
    async def test_analyze_floor_plan(self, mock_analyze, client: AsyncClient, auth_headers: dict):
        """Test floor plan analysis"""
        mock_analyze.return_value = {
            "rooms_detected": [
                {"name": "Living Room", "area": 25.5, "dimensions": "5m x 5.1m"},
                {"name": "Kitchen", "area": 12.0, "dimensions": "3m x 4m"}
            ],
            "total_area": 37.5,
            "room_count": 2,
            "confidence_score": 0.92
        }
        
        # Upload a floor plan
        file_content = b"Floor plan image content"
        files = {"file": ("floorplan.png", io.BytesIO(file_content), "image/png")}
        data = {"title": "Floor Plan", "document_type": "floor_plan"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Analyze floor plan
        response = await client.post(f"/api/v1/documents/{document_id}/analyze-floor-plan", headers=auth_headers)
        assert response.status_code == 200
        
        analysis = response.json()
        assert "rooms_detected" in analysis
        assert "total_area" in analysis
        assert len(analysis["rooms_detected"]) == 2
        assert analysis["total_area"] == 37.5

    async def test_document_search(self, client: AsyncClient, auth_headers: dict):
        """Test document search functionality"""
        # Upload some documents first
        docs_to_create = [
            {"title": "Living Room Plans", "filename": "living_room.pdf"},
            {"title": "Kitchen Design", "filename": "kitchen.pdf"},
            {"title": "Bathroom Layout", "filename": "bathroom.pdf"}
        ]
        
        for doc_data in docs_to_create:
            file_content = f"Content for {doc_data['title']}".encode()
            files = {"file": (doc_data['filename'], io.BytesIO(file_content), "application/pdf")}
            data = {"title": doc_data['title']}
            
            await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        
        # Search for documents
        response = await client.get("/api/v1/documents/?search=kitchen", headers=auth_headers)
        assert response.status_code == 200
        
        documents = response.json()
        # Should find the kitchen document
        kitchen_docs = [doc for doc in documents if "kitchen" in doc["title"].lower()]
        assert len(kitchen_docs) >= 1

    async def test_document_filtering_by_type(self, client: AsyncClient, auth_headers: dict):
        """Test filtering documents by file type"""
        # Upload documents of different types
        file_types = [
            ("test.pdf", "application/pdf"),
            ("test.png", "image/png"),
            ("test.jpg", "image/jpeg")
        ]
        
        for filename, content_type in file_types:
            file_content = f"Content for {filename}".encode()
            files = {"file": (filename, io.BytesIO(file_content), content_type)}
            data = {"title": f"Test {filename}"}
            
            await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        
        # Filter by PDF files
        response = await client.get("/api/v1/documents/?file_type=application/pdf", headers=auth_headers)
        assert response.status_code == 200
        
        documents = response.json()
        # All returned documents should be PDFs
        for doc in documents:
            if doc["title"].startswith("Test "):  # Our test documents
                assert doc["file_type"] == "application/pdf"

    async def test_document_access_control(self, client: AsyncClient, auth_headers: dict):
        """Test that users can only access their own documents"""
        # Upload a document
        file_content = b"Private document content"
        files = {"file": ("private.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"title": "Private Document"}
        
        upload_response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
        document_id = upload_response.json()["id"]
        
        # Create another user
        other_user_data = {
            "email": "other2@example.com",
            "username": "otheruser2",
            "password": "password123",
            "phone_number": "+1234567892",
            "company_name": "Other Company 2"
        }
        
        await client.post("/api/v1/auth/register", json=other_user_data)
        
        # Login as other user
        login_data = {
            "username": "other2@example.com",
            "password": "password123"
        }
        
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Try to access the original user's document
        response = await client.get(f"/api/v1/documents/{document_id}", headers=other_headers)
        assert response.status_code == 404  # Should not find document from other user

    async def test_bulk_document_operations(self, client: AsyncClient, auth_headers: dict):
        """Test bulk document operations"""
        # Upload multiple documents
        document_ids = []
        for i in range(3):
            file_content = f"Bulk test document {i}".encode()
            files = {"file": (f"bulk_{i}.pdf", io.BytesIO(file_content), "application/pdf")}
            data = {"title": f"Bulk Document {i}"}
            
            response = await client.post("/api/v1/documents/upload", files=files, data=data, headers=auth_headers)
            document_ids.append(response.json()["id"])
        
        # Bulk delete
        bulk_data = {"document_ids": document_ids}
        response = await client.post("/api/v1/documents/bulk-delete", json=bulk_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Verify documents are deleted
        for doc_id in document_ids:
            get_response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
            assert get_response.status_code == 404