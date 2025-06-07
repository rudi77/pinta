from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_premium: bool
    premium_until: Optional[datetime]
    quotes_this_month: int
    additional_quotes: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Quote schemas
class QuoteItemBase(BaseModel):
    position: int
    description: str
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    room_name: Optional[str] = None
    area_sqm: Optional[float] = None
    work_type: Optional[str] = None

class QuoteItemCreate(QuoteItemBase):
    pass

class QuoteItemResponse(QuoteItemBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class QuoteBase(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    project_title: str = Field(..., min_length=1, max_length=200)
    project_description: Optional[str] = None

class QuoteCreate(QuoteBase):
    quote_items: List[QuoteItemCreate] = []

class QuoteUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    project_title: Optional[str] = None
    project_description: Optional[str] = None
    status: Optional[str] = None

class QuoteResponse(QuoteBase):
    id: int
    quote_number: str
    total_amount: Optional[float]
    labor_hours: Optional[float]
    hourly_rate: Optional[float]
    material_cost: Optional[float]
    additional_costs: Optional[float]
    status: str
    ai_processing_status: str
    created_at: datetime
    updated_at: datetime
    quote_items: List[QuoteItemResponse] = []
    
    class Config:
        from_attributes = True

# AI schemas
class AIAnalysisRequest(BaseModel):
    input_text: str = Field(..., min_length=1)
    context: Optional[str] = "initial_input"

class AIAnalysisResponse(BaseModel):
    success: bool
    confidence: float
    extracted_data: dict
    questions: List[str]
    suggested_items: List[dict]

# Document schemas
class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: Optional[int]
    mime_type: Optional[str]
    extracted_text: Optional[str]
    analysis_result: Optional[str]
    processing_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Payment schemas
class PaymentCreate(BaseModel):
    amount: float
    payment_type: str
    description: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    amount: float
    currency: str
    status: str
    payment_type: str
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Generic response schemas
class SuccessResponse(BaseModel):
    success: bool = True
    message: str

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# AI Schemas
class AIAnalysisRequest(BaseModel):
    description: str
    context: Optional[str] = "initial_input"

class AIQuestion(BaseModel):
    id: str
    question: str
    type: str  # "multiple_choice", "text", "number"
    options: Optional[List[str]] = None

class AIAnalysisResponse(BaseModel):
    analysis: Dict[str, Any]
    questions: List[AIQuestion]
    suggestions: List[str]
    success: bool = True

class AIFollowUpRequest(BaseModel):
    message: str
    conversation_history: List[Dict[str, Any]] = []

class AIQuestionResponse(BaseModel):
    response: str
    needs_more_info: bool
    suggested_questions: List[str] = []
    success: bool = True

class AIQuoteGenerationRequest(BaseModel):
    project_data: Dict[str, Any]
    answers: List[Dict[str, Any]]

class GenerateQuoteAIRequest(BaseModel):
    project_description: str = Field(..., min_length=1)

class AIQuoteItem(BaseModel):
    description: str
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    category: str

class AIQuoteData(BaseModel):
    project_title: str
    total_amount: float
    labor_hours: float
    hourly_rate: float
    material_cost: float
    additional_costs: float

class AIQuoteGenerationResponse(BaseModel):
    quote: AIQuoteData
    items: List[AIQuoteItem]
    notes: str
    recommendations: List[str]
    success: bool = True

