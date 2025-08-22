import pytest
import tempfile
import os
import json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from unittest.mock import patch, MagicMock
import asyncio

from src.services.document_service import DocumentProcessor, document_processor
from src.routes.documents import extract_room_info, extract_measurements

@pytest.fixture
def doc_processor():
    return DocumentProcessor()

@pytest.fixture
def sample_text_image():
    """Create a sample image with German text"""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add some German text
    text_lines = [
        "Wohnzimmer: 25 m² groß",
        "Schlafzimmer: 15 qm",
        "Küche: 12,5 Quadratmeter",
        "Bad: 8 m²",
        "Höhe: 2,50 m",
        "Länge: 5,2 m x Breite: 4,8 m"
    ]
    
    y_position = 50
    for line in text_lines:
        draw.text((50, y_position), line, fill='black')
        y_position += 40
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file.name, 'PNG')
    temp_file.close()
    
    return temp_file.name

@pytest.fixture
def sample_handwriting_image():
    """Create a sample image simulating handwritten text"""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Simulate handwriting with irregular text
    handwritten_text = [
        "Raum 1: ca. 20qm",
        "Wände: 3x streichen",
        "Farbe: weiß",
        "Notizen: Spachteln nötig"
    ]
    
    y_position = 100
    for i, line in enumerate(handwritten_text):
        # Vary the x position to simulate handwriting irregularity
        x_position = 60 + (i * 10) % 30
        draw.text((x_position, y_position), line, fill='black')
        y_position += 60
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file.name, 'PNG')
    temp_file.close()
    
    return temp_file.name

@pytest.mark.asyncio
async def test_file_validation(doc_processor, sample_text_image):
    """Test file validation functionality"""
    
    # Test valid file
    result = doc_processor.validate_file(sample_text_image, "test.png")
    assert result["valid"] is True
    assert result["file_size"] > 0
    
    # Test invalid file extension
    result = doc_processor.validate_file(sample_text_image, "test.xyz")
    assert result["valid"] is False
    assert "Unsupported format" in result["error"]
    
    # Test non-existent file
    result = doc_processor.validate_file("/non/existent/file.png", "test.png")
    assert result["valid"] is False
    assert "File not found" in result["error"]

@pytest.mark.asyncio
async def test_image_preprocessing(doc_processor, sample_text_image):
    """Test image preprocessing"""
    
    original_img = Image.open(sample_text_image)
    
    # Test basic preprocessing
    processed_img = await doc_processor._preprocess_image(original_img, {})
    
    assert processed_img is not None
    assert processed_img.mode == 'RGB'
    
    # Test with grayscale option
    processed_img_gray = await doc_processor._preprocess_image(original_img, {"grayscale": True})
    assert processed_img_gray is not None

@pytest.mark.asyncio
async def test_hash_generation(doc_processor, sample_text_image):
    """Test file hash generation"""
    
    hash1 = await doc_processor._generate_file_hash(sample_text_image)
    hash2 = await doc_processor._generate_file_hash(sample_text_image)
    
    assert hash1 == hash2  # Same file should produce same hash
    assert len(hash1) == 16  # Should be 16 characters (first 16 of SHA-256)
    assert hash1.isalnum()  # Should be alphanumeric

@pytest.mark.asyncio
async def test_ocr_tesseract_german(doc_processor, sample_text_image):
    """Test Tesseract OCR with German text"""
    
    image = Image.open(sample_text_image)
    
    # Mock pytesseract to avoid dependency on actual Tesseract installation
    with patch('src.services.document_service.pytesseract.image_to_data') as mock_tesseract:
        mock_tesseract.return_value = {
            'text': ['Wohnzimmer:', '25', 'm²', 'groß', 'Schlafzimmer:', '15', 'qm'],
            'conf': [85, 90, 88, 82, 87, 85, 89]
        }
        
        result = await doc_processor._ocr_tesseract_german(image, {})
        
        assert result["method"] == "tesseract_german"
        assert result["confidence"] > 0
        assert "Wohnzimmer" in result["text"]
        assert result["word_count"] > 0

@pytest.mark.asyncio
async def test_easyocr_processing(doc_processor, sample_text_image):
    """Test EasyOCR processing"""
    
    image = Image.open(sample_text_image)
    
    # Mock EasyOCR reader
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [
        ([(0, 0), (100, 0), (100, 30), (0, 30)], 'Wohnzimmer: 25 m²', 0.95),
        ([(0, 40), (100, 40), (100, 70), (0, 70)], 'Schlafzimmer: 15 qm', 0.87)
    ]
    
    doc_processor.easyocr_reader = mock_reader
    
    result = await doc_processor._ocr_easyocr(image, {})
    
    assert result["method"] == "easyocr"
    assert result["confidence"] > 0
    assert "Wohnzimmer" in result["text"]
    assert result["word_count"] == 2

@pytest.mark.asyncio
async def test_process_image(doc_processor, sample_text_image):
    """Test complete image processing"""
    
    # Mock both OCR methods
    with patch.object(doc_processor, '_ocr_tesseract_german') as mock_tesseract, \
         patch.object(doc_processor, '_ocr_easyocr') as mock_easyocr:
        
        mock_tesseract.return_value = {
            "method": "tesseract_german",
            "text": "Wohnzimmer 25 m²",
            "confidence": 85.0,
            "handwriting_detected": False
        }
        
        mock_easyocr.return_value = {
            "method": "easyocr",
            "text": "Wohnzimmer 25 m²",
            "confidence": 90.0,
            "handwriting_detected": False
        }
        
        doc_processor.easyocr_reader = MagicMock()  # Mock reader exists
        
        result = await doc_processor._process_image(sample_text_image, "test.png", {})
        
        assert result["processing_method"] == "image_advanced"
        assert result["extracted_text"] == "Wohnzimmer 25 m²"
        assert result["text_confidence"] == 90.0  # Should pick the higher confidence
        assert len(result["pages"]) == 1

@pytest.mark.asyncio
async def test_batch_processing(doc_processor, sample_text_image, sample_handwriting_image):
    """Test batch processing of multiple documents"""
    
    with patch.object(doc_processor, 'process_document') as mock_process:
        mock_process.side_effect = [
            {"success": True, "extracted_text": "Document 1 text", "text_confidence": 85.0},
            {"success": True, "extracted_text": "Document 2 text", "text_confidence": 75.0}
        ]
        
        results = await doc_processor.process_batch(
            [sample_text_image, sample_handwriting_image],
            ["doc1.png", "doc2.png"],
            ["image/png", "image/png"],
            user_id=1,
            processing_options={}
        )
        
        assert len(results) == 2
        assert all(r.get("success", True) for r in results)
        assert mock_process.call_count == 2

@pytest.mark.asyncio
async def test_batch_processing_with_limit(doc_processor):
    """Test batch processing with file limit"""
    
    # Create list of 11 files (exceeds limit of 10)
    file_paths = [f"/fake/path/{i}.png" for i in range(11)]
    filenames = [f"file{i}.png" for i in range(11)]
    content_types = ["image/png"] * 11
    
    with pytest.raises(ValueError, match="Maximum 10 documents allowed per batch"):
        await doc_processor.process_batch(
            file_paths, filenames, content_types, user_id=1
        )

def test_extract_room_info():
    """Test room information extraction from text"""
    
    text = "Das Wohnzimmer ist 25 m² groß. Das Schlafzimmer hat 15 qm. Auch ein kleines Badezimmer ist vorhanden."
    
    rooms = extract_room_info(text.lower())
    
    assert len(rooms) > 0
    assert any("wohnzimmer" in room.lower() for room in rooms)
    assert any("schlafzimmer" in room.lower() for room in rooms)
    assert any("badezimmer" in room.lower() for room in rooms)

def test_extract_measurements():
    """Test measurement extraction from text"""
    
    text = "Raum: 25 m², Höhe: 2,5 m, Breite: 3,2 m, Länge: 4,8m, Fläche: 15,36 qm"
    
    measurements = extract_measurements(text.lower())
    
    assert len(measurements) > 0
    
    # Check for area measurements
    area_measurements = [m for m in measurements if m.get("unit") in ["m²", "qm", "quadratmeter"]]
    assert len(area_measurements) > 0
    
    # Check for length measurements
    length_measurements = [m for m in measurements if m.get("unit") in ["m", "meter"]]
    assert len(length_measurements) > 0

@pytest.mark.asyncio
async def test_document_processing_cache(doc_processor, sample_text_image):
    """Test caching of document processing results"""
    
    from src.core.cache import cache_service
    
    # Mock cache service
    cache_service.get_cached_quote_analysis = MagicMock(return_value=None)
    cache_service.cache_quote_analysis = MagicMock()
    
    with patch.object(doc_processor, '_process_image') as mock_process:
        mock_process.return_value = {
            "extracted_text": "Cached result",
            "text_confidence": 85.0
        }
        
        result = await doc_processor.process_document(
            sample_text_image, "test.png", "image/png", user_id=1
        )
        
        # Should process and cache the result
        assert mock_process.called
        assert cache_service.cache_quote_analysis.called
        
        # Test cache hit
        cache_service.get_cached_quote_analysis.return_value = {
            "extracted_text": "Cached result",
            "cached": True
        }
        
        cached_result = await doc_processor.process_document(
            sample_text_image, "test.png", "image/png", user_id=1
        )
        
        assert cached_result.get("cached") is True

@pytest.mark.asyncio
async def test_handwriting_detection():
    """Test handwriting detection in documents"""
    
    with patch('src.services.document_service.pytesseract.image_to_data') as mock_tesseract:
        # Simulate low confidence scores typical of handwritten text
        mock_tesseract.return_value = {
            'text': ['handwritten', 'notes', 'here'],
            'conf': [45, 52, 38]  # Low confidence scores
        }
        
        doc_processor = DocumentProcessor()
        image = Image.new('RGB', (200, 100), 'white')
        
        result = await doc_processor._ocr_tesseract_german(image, {})
        
        # Should detect handwriting due to low confidence
        assert result["handwriting_detected"] is True
        assert result["confidence"] < 70

@pytest.mark.asyncio
async def test_error_handling(doc_processor):
    """Test error handling in document processing"""
    
    # Test processing non-existent file
    result = await doc_processor.process_document(
        "/non/existent/file.png",
        "test.png", 
        "image/png",
        user_id=1
    )
    
    assert result["success"] is False
    assert "error" in result

def test_supported_formats(doc_processor):
    """Test supported file formats"""
    
    assert '.png' in doc_processor.supported_formats['image']
    assert '.jpg' in doc_processor.supported_formats['image']
    assert '.pdf' in doc_processor.supported_formats['pdf']
    assert '.webp' in doc_processor.supported_formats['image']

# Cleanup fixtures
def cleanup_temp_files(*file_paths):
    """Clean up temporary files created during tests"""
    for file_path in file_paths:
        try:
            os.unlink(file_path)
        except:
            pass

@pytest.fixture(autouse=True)
def cleanup_after_test(sample_text_image, sample_handwriting_image):
    """Automatically cleanup temp files after each test"""
    yield
    cleanup_temp_files(sample_text_image, sample_handwriting_image)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])