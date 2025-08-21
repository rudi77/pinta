from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum

# Base Models
class UserBase(BaseModel):
    email: EmailStr
    username: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class QuoteBase(BaseModel):
    customer_name: str
    project_title: str
    project_description: str
    total_amount: float
    status: str = "draft"
    created_by_ai: bool = False
    conversation_history: Optional[str] = None

class QuoteItemBase(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total_price: float

class PaymentBase(BaseModel):
    amount: float
    status: str
    payment_method: str

# Error Models
class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None

# AI Models
class AIConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AIConversationHistory(BaseModel):
    messages: List[AIConversationMessage]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Intelligent Follow-up Question Models
class QuestionType(str, Enum):
    multiple_choice = "multiple_choice"
    text = "text"
    number = "number"
    yes_no = "yes_no"

class QuestionImportance(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class IntelligentQuestion(BaseModel):
    id: str
    question: str
    type: QuestionType
    importance: QuestionImportance
    options: Optional[List[str]] = None

class CompletionStatus(BaseModel):
    estimated_completeness: int = Field(ge=0, le=100, description="Percentage of information completeness")
    missing_critical_info: List[str] = Field(default_factory=list)
    ready_for_quote: bool = False

class IntelligentFollowUpResponse(BaseModel):
    response: str
    has_follow_up_questions: bool
    questions: List[IntelligentQuestion] = Field(default_factory=list)
    completion_status: CompletionStatus
    suggestions: List[str] = Field(default_factory=list)

class IntelligentFollowUpRequest(BaseModel):
    message: str
    conversation_id: str = "default"
    context: Optional[Dict[str, Any]] = None

# Professional PDF Generation Models
class PDFGenerationOptions(BaseModel):
    include_signature: bool = True
    include_logo: bool = True
    include_terms: bool = True
    custom_footer: Optional[str] = None

class PDFGenerationResponse(BaseModel):
    success: bool
    message: str
    pdf_info: Optional[Dict[str, Any]] = None

class ExportOptions(BaseModel):
    format_type: str = Field(default="pdf", description="Export format: pdf, json, csv")
    include_signature: bool = True
    include_logo: bool = True

class ExportResponse(BaseModel):
    success: bool
    message: str
    export_info: Optional[Dict[str, Any]] = None

class AIAnalysisRequest(BaseModel):
    input: str
    conversation_history: Optional[List[AIConversationMessage]] = None

class AIAnalysisResponse(BaseModel):
    analysis: Dict[str, Any]
    questions: List[Dict[str, Any]]
    suggestions: List[str]
    conversation_history: List[AIConversationMessage]

class AIFollowUpRequest(BaseModel):
    question: str
    conversation_history: List[AIConversationMessage]

class AIQuestionResponse(BaseModel):
    response: str
    needs_more_info: bool
    conversation_history: List[AIConversationMessage]

class GenerateQuoteAIRequest(BaseModel):
    project_data: Dict[str, Any]
    answers: List[Dict[str, Any]]
    conversation_history: List[AIConversationMessage]

class AIQuoteGenerationRequest(BaseModel):
    project_data: Dict[str, Any]
    answers: List[Dict[str, Any]]
    conversation_history: List[AIConversationMessage]
    customer_name: str
    customer_address: str
    customer_email: str
    customer_phone: str

class AIQuoteGenerationResponse(BaseModel):
    quote: Dict[str, Any]
    items: List[Dict[str, Any]]
    total_amount: float
    conversation_history: List[AIConversationMessage]
    pdf_url: Optional[str] = None

# Create Models
class UserCreate(UserBase):
    password: str

class QuoteCreate(QuoteBase):
    items: List[QuoteItemBase]
    conversation_history: Optional[List[AIConversationMessage]] = None

class QuoteItemCreate(QuoteItemBase):
    pass

class PaymentCreate(PaymentBase):
    quote_id: int

# Update Models
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None

class QuoteUpdate(QuoteBase):
    items: Optional[List[QuoteItemBase]] = None
    conversation_history: Optional[List[AIConversationMessage]] = None

class QuoteItemUpdate(QuoteItemBase):
    pass

class PaymentUpdate(PaymentBase):
    pass

# Response Models
class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_premium: bool = False
    premium_until: Optional[datetime] = None
    quotes_this_month: int = 0
    additional_quotes: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QuoteItemResponse(QuoteItemBase):
    id: int
    quote_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QuoteResponse(QuoteBase):
    id: int
    quote_number: str
    user_id: int
    items: List[QuoteItemResponse]
    created_at: datetime
    updated_at: datetime
    created_by_ai: bool
    conversation_history: Optional[List[AIConversationMessage]] = None

    class Config:
        from_attributes = True

class PaymentResponse(PaymentBase):
    id: int
    quote_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Auth Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class SuccessResponse(BaseModel):
    message: str

# Document Models
class DocumentBase(BaseModel):
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    processing_status: str = "pending"
    quote_id: Optional[int] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    processing_status: Optional[str] = None
    analysis_result: Optional[Dict[str, Any]] = None

class DocumentResponse(DocumentBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    analysis_result: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class Document(BaseModel):
    id: int
    user_id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    processing_status: str
    analysis_result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 