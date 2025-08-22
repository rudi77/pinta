import os
import logging
import asyncio
import tempfile
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import re

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import pdf2image
from pdf2image import convert_from_path
import pandas as pd
try:
    import pdfplumber  # Replacement for camelot
except ImportError:
    pdfplumber = None
try:
    import tabula
except ImportError:
    tabula = None
try:
    import easyocr
except ImportError:
    easyocr = None

from src.core.settings import settings
from src.core.cache import cache_service

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Advanced document processing with OCR, table extraction, and handwriting recognition"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.supported_formats = {
            'image': ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'],
            'pdf': ['.pdf'],
            'document': ['.docx', '.doc', '.txt']
        }
        
        # Initialize EasyOCR for better German support and handwriting
        self.easyocr_reader = None
        self._init_easyocr()
    
    def _init_easyocr(self):
        """Initialize EasyOCR reader for German text and handwriting"""
        try:
            if easyocr is not None:
                # Support for German and English, with handwriting model
                self.easyocr_reader = easyocr.Reader(['de', 'en'])
                logger.info("EasyOCR initialized successfully for German/English")
            else:
                logger.warning("EasyOCR not available, skipping initialization")
                self.easyocr_reader = None
        except Exception as e:
            logger.warning(f"EasyOCR initialization failed: {e}")
            self.easyocr_reader = None
    
    async def process_document(self, file_path: str, filename: str, content_type: str, 
                             user_id: int, processing_options: Dict = None) -> Dict:
        """Process document with advanced OCR and extraction"""
        
        processing_options = processing_options or {}
        
        try:
            # Generate processing cache key
            file_hash = await self._generate_file_hash(file_path)
            cache_key = f"document_processing:{file_hash}:{json.dumps(processing_options, sort_keys=True)}"
            
            # Check cache first
            cached_result = await cache_service.get_cached_quote_analysis(cache_key)
            if cached_result:
                logger.info(f"Using cached document processing result for {filename}")
                return cached_result
            
            logger.info(f"Processing document: {filename} for user {user_id}")
            
            # Determine file type and processing strategy
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext in self.supported_formats['pdf']:
                result = await self._process_pdf(file_path, filename, processing_options)
            elif file_ext in self.supported_formats['image']:
                result = await self._process_image(file_path, filename, processing_options)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
            
            # Add metadata
            result.update({
                "filename": filename,
                "file_type": file_ext,
                "processed_at": datetime.now().isoformat(),
                "user_id": user_id,
                "file_hash": file_hash
            })
            
            # Cache result for 6 hours
            await cache_service.cache_quote_analysis(cache_key, result, ttl=21600)
            
            logger.info(f"Document processing completed for {filename}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            return {
                "error": str(e),
                "filename": filename,
                "processed_at": datetime.now().isoformat(),
                "success": False
            }
    
    async def _process_pdf(self, file_path: str, filename: str, options: Dict) -> Dict:
        """Process PDF with table extraction and OCR"""
        
        results = {
            "pages": [],
            "tables": [],
            "extracted_text": "",
            "text_confidence": 0.0,
            "handwriting_detected": False,
            "processing_method": "pdf_advanced"
        }
        
        try:
            # Convert PDF to images for OCR
            images = await self._pdf_to_images(file_path)
            
            # Process each page
            for page_num, image in enumerate(images, 1):
                page_result = await self._process_page_image(image, page_num, options)
                results["pages"].append(page_result)
                
                # Accumulate text
                if page_result.get("text"):
                    results["extracted_text"] += f"\n--- Seite {page_num} ---\n"
                    results["extracted_text"] += page_result["text"]
                
                # Update confidence (average)
                if page_result.get("confidence", 0) > 0:
                    results["text_confidence"] += page_result["confidence"]
                
                # Check for handwriting
                if page_result.get("handwriting_detected"):
                    results["handwriting_detected"] = True
            
            # Calculate average confidence
            if results["pages"]:
                results["text_confidence"] = results["text_confidence"] / len(results["pages"])
            
            # Extract tables using Camelot and Tabula
            try:
                await self._extract_pdf_tables(file_path, results)
            except Exception as e:
                logger.warning(f"Table extraction failed for {filename}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"PDF processing failed for {filename}: {e}")
            raise
    
    async def _process_image(self, file_path: str, filename: str, options: Dict) -> Dict:
        """Process single image with advanced OCR"""
        
        try:
            # Load and preprocess image
            image = Image.open(file_path)
            preprocessed_image = await self._preprocess_image(image, options)
            
            # Process with OCR
            result = await self._process_page_image(preprocessed_image, 1, options)
            
            return {
                "pages": [result],
                "extracted_text": result.get("text", ""),
                "text_confidence": result.get("confidence", 0.0),
                "handwriting_detected": result.get("handwriting_detected", False),
                "processing_method": "image_advanced"
            }
            
        except Exception as e:
            logger.error(f"Image processing failed for {filename}: {e}")
            raise
    
    async def _process_page_image(self, image: Image.Image, page_num: int, options: Dict) -> Dict:
        """Process single page/image with multiple OCR engines"""
        
        page_result = {
            "page_number": page_num,
            "text": "",
            "confidence": 0.0,
            "handwriting_detected": False,
            "ocr_methods": []
        }
        
        # Method 1: Tesseract with German optimization
        tesseract_result = await self._ocr_tesseract_german(image, options)
        page_result["ocr_methods"].append(tesseract_result)
        
        # Method 2: EasyOCR for better handwriting and challenging text
        if self.easyocr_reader:
            easyocr_result = await self._ocr_easyocr(image, options)
            page_result["ocr_methods"].append(easyocr_result)
        
        # Select best result based on confidence
        best_result = max(page_result["ocr_methods"], 
                         key=lambda x: x.get("confidence", 0))
        
        page_result.update({
            "text": best_result.get("text", ""),
            "confidence": best_result.get("confidence", 0.0),
            "handwriting_detected": best_result.get("handwriting_detected", False),
            "best_method": best_result.get("method", "unknown")
        })
        
        return page_result
    
    async def _ocr_tesseract_german(self, image: Image.Image, options: Dict) -> Dict:
        """OCR with Tesseract optimized for German"""
        
        try:
            # Configure Tesseract for German
            custom_config = r'''
                -l deu
                --oem 3
                --psm 6
                -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzäöüßÄÖÜ.,!?()-+*/=€$%&@#:;'"
            '''
            
            # Extract text with confidence
            data = pytesseract.image_to_data(
                image, 
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate confidence and extract text
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract text
            text_parts = []
            for i, word in enumerate(data['text']):
                if data['conf'][i] > 30:  # Only include confident words
                    text_parts.append(word)
            
            extracted_text = ' '.join(text_parts)
            
            # Check for handwriting indicators (low confidence, irregular spacing)
            handwriting_detected = avg_confidence < 70 and len(confidences) > 10
            
            return {
                "method": "tesseract_german",
                "text": extracted_text,
                "confidence": avg_confidence,
                "handwriting_detected": handwriting_detected,
                "word_count": len([w for w in text_parts if w.strip()])
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return {
                "method": "tesseract_german",
                "text": "",
                "confidence": 0.0,
                "handwriting_detected": False,
                "error": str(e)
            }
    
    async def _ocr_easyocr(self, image: Image.Image, options: Dict) -> Dict:
        """OCR with EasyOCR for better handwriting support"""
        
        try:
            if not self.easyocr_reader:
                return {
                    "method": "easyocr",
                    "text": "",
                    "confidence": 0.0,
                    "handwriting_detected": False,
                    "error": "EasyOCR not available"
                }
            
            # Convert PIL image to numpy array
            image_np = np.array(image)
            
            # Run EasyOCR
            results = self.easyocr_reader.readtext(image_np, detail=1)
            
            # Process results
            text_parts = []
            confidences = []
            
            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # Lower threshold for handwriting
                    text_parts.append(text)
                    confidences.append(confidence * 100)  # Convert to percentage
            
            extracted_text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # EasyOCR is generally better with handwriting
            # Check for mixed confidence levels as indicator
            confidence_variance = np.var(confidences) if confidences else 0
            handwriting_detected = confidence_variance > 200 or avg_confidence < 60
            
            return {
                "method": "easyocr",
                "text": extracted_text,
                "confidence": avg_confidence,
                "handwriting_detected": handwriting_detected,
                "word_count": len(text_parts)
            }
            
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return {
                "method": "easyocr",
                "text": "",
                "confidence": 0.0,
                "handwriting_detected": False,
                "error": str(e)
            }
    
    async def _preprocess_image(self, image: Image.Image, options: Dict) -> Image.Image:
        """Advanced image preprocessing for better OCR"""
        
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too small or too large
            width, height = image.size
            if width < 800 or height < 600:
                # Upscale small images
                scale_factor = max(800/width, 600/height)
                new_size = (int(width * scale_factor), int(height * scale_factor))
                image = image.resize(new_size, Image.LANCZOS)
            elif width > 3000 or height > 3000:
                # Downscale very large images
                scale_factor = min(3000/width, 3000/height)
                new_size = (int(width * scale_factor), int(height * scale_factor))
                image = image.resize(new_size, Image.LANCZOS)
            
            # Enhance contrast and sharpness
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Optional: Convert to grayscale for better OCR
            if options.get('grayscale', True):
                image = image.convert('L')
                image = image.convert('RGB')  # Convert back for consistency
            
            return image
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")
            return image  # Return original if preprocessing fails
    
    async def _pdf_to_images(self, file_path: str, dpi: int = 300) -> List[Image.Image]:
        """Convert PDF pages to images"""
        
        try:
            # Convert PDF to images with high DPI for better OCR
            images = convert_from_path(
                file_path,
                dpi=dpi,
                fmt='RGB',
                thread_count=2  # Limit threads to avoid memory issues
            )
            
            logger.info(f"Converted PDF to {len(images)} images")
            return images
            
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise
    
    async def _extract_pdf_tables(self, file_path: str, results: Dict):
        """Extract tables from PDF using multiple methods"""
        
        try:
            # Method 1: Camelot (better for structured tables)
            try:
                tables = camelot.read_pdf(file_path, pages='all', flavor='lattice')
                
                for i, table in enumerate(tables):
                    if table.df.shape[0] > 1 and table.df.shape[1] > 1:  # Valid table
                        table_data = {
                            "table_id": i + 1,
                            "method": "camelot_lattice",
                            "accuracy": table.accuracy,
                            "data": table.df.to_dict('records'),
                            "shape": table.df.shape,
                            "page": table.page
                        }
                        results["tables"].append(table_data)
                
                logger.info(f"Camelot extracted {len(tables)} tables")
                
            except Exception as e:
                logger.warning(f"Camelot table extraction failed: {e}")
            
            # Method 2: Tabula (fallback for different table types)
            try:
                tabula_tables = tabula.read_pdf(file_path, pages='all', multiple_tables=True)
                
                for i, df in enumerate(tabula_tables):
                    if df.shape[0] > 1 and df.shape[1] > 1:  # Valid table
                        table_data = {
                            "table_id": len(results["tables"]) + 1,
                            "method": "tabula",
                            "accuracy": 0.8,  # Default accuracy for tabula
                            "data": df.to_dict('records'),
                            "shape": df.shape,
                            "page": "unknown"
                        }
                        results["tables"].append(table_data)
                
                logger.info(f"Tabula extracted {len(tabula_tables)} additional tables")
                
            except Exception as e:
                logger.warning(f"Tabula table extraction failed: {e}")
                
        except Exception as e:
            logger.error(f"Table extraction completely failed: {e}")
    
    async def _generate_file_hash(self, file_path: str) -> str:
        """Generate SHA-256 hash of file for caching"""
        
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()[:16]  # Use first 16 chars
        except Exception as e:
            logger.warning(f"File hashing failed: {e}")
            return f"hash_error_{datetime.now().timestamp()}"
    
    def validate_file(self, file_path: str, filename: str, max_size_mb: int = 50) -> Dict:
        """Validate uploaded file"""
        
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return {"valid": False, "error": "File not found"}
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > max_size_mb * 1024 * 1024:
                return {"valid": False, "error": f"File too large (max {max_size_mb}MB)"}
            
            # Check file extension
            file_ext = os.path.splitext(filename)[1].lower()
            all_supported = []
            for formats in self.supported_formats.values():
                all_supported.extend(formats)
            
            if file_ext not in all_supported:
                return {"valid": False, "error": f"Unsupported format: {file_ext}"}
            
            # Additional validation for images
            if file_ext in self.supported_formats['image']:
                try:
                    with Image.open(file_path) as img:
                        # Check image size
                        width, height = img.size
                        if width < 100 or height < 100:
                            return {"valid": False, "error": "Image too small (min 100x100)"}
                        if width > 10000 or height > 10000:
                            return {"valid": False, "error": "Image too large (max 10000x10000)"}
                except Exception:
                    return {"valid": False, "error": "Invalid or corrupted image file"}
            
            return {"valid": True, "file_size": file_size}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation failed: {str(e)}"}
    
    async def process_batch(self, file_paths: List[str], filenames: List[str], 
                          content_types: List[str], user_id: int, 
                          processing_options: Dict = None) -> List[Dict]:
        """Process multiple documents in batch (max 10)"""
        
        if len(file_paths) > 10:
            raise ValueError("Maximum 10 documents allowed per batch")
        
        logger.info(f"Starting batch processing of {len(file_paths)} documents for user {user_id}")
        
        # Process documents concurrently with semaphore to limit parallel processing
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent processes
        
        async def process_single(file_path: str, filename: str, content_type: str):
            async with semaphore:
                return await self.process_document(
                    file_path, filename, content_type, user_id, processing_options
                )
        
        # Create tasks for concurrent processing
        tasks = []
        for file_path, filename, content_type in zip(file_paths, filenames, content_types):
            task = process_single(file_path, filename, content_type)
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "filename": filenames[i],
                    "error": str(result),
                    "success": False,
                    "processed_at": datetime.now().isoformat()
                })
            else:
                processed_results.append(result)
        
        logger.info(f"Batch processing completed. Success: {sum(1 for r in processed_results if r.get('success', True))}/{len(processed_results)}")
        
        return processed_results

# Global document processor instance
document_processor = DocumentProcessor()