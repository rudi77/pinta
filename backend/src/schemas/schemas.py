from typing import Annotated, Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum

# Reusable cost parameter types
HourlyRate = Annotated[Optional[float], Field(None, ge=0, le=500, description="Stundensatz EUR/h netto")]
MaterialCostMarkup = Annotated[Optional[float], Field(None, ge=0, le=100, description="Materialaufschlag in Prozent")]

# Base Models
class UserBase(BaseModel):
    email: EmailStr
    username: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class QuoteBase(BaseModel):
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
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
    position: Optional[int] = None
    unit: Optional[str] = "Stk"
    room_name: Optional[str] = None
    area_sqm: Optional[float] = None
    work_type: Optional[str] = None

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

# Quota Management Models
class QuotaUsage(BaseModel):
    used: int
    limit: int
    remaining: int
    percentage: float
    additional_available: Optional[int] = 0

class QuotaLimits(BaseModel):
    quotes_per_month: int
    documents_per_month: int
    api_requests_per_day: int
    storage_mb: int

class QuotaWarning(BaseModel):
    type: str
    resource: str
    percentage: float
    message: str
    action: str

class QuotaStatus(BaseModel):
    user_id: int
    is_premium: bool
    premium_until: Optional[str] = None
    limits: QuotaLimits
    usage: Dict[str, QuotaUsage]
    warnings: List[QuotaWarning]
    period: Dict[str, str]
    last_updated: str

class QuotaCheckRequest(BaseModel):
    resource_type: str = Field(description="Resource type: quotes, documents, api_requests, storage")
    amount: int = Field(default=1, ge=1, description="Amount to check")

class QuotaConsumeRequest(BaseModel):
    resource_type: str = Field(description="Resource type: quotes, documents, api_requests, storage")
    amount: int = Field(default=1, ge=1, description="Amount to consume")
    metadata: Optional[Dict[str, Any]] = None

class UsageHistoryResponse(BaseModel):
    id: int
    resource_type: str
    action: str
    amount: int
    metadata: Optional[str] = None
    created_at: str
    ip_address: Optional[str] = None

class QuotaNotificationResponse(BaseModel):
    id: int
    notification_type: str
    resource_type: str
    threshold_percentage: float
    message: str
    is_read: bool
    sent_at: Optional[str] = None
    created_at: str

class QuotaSettingsUpdate(BaseModel):
    quota_warnings_enabled: Optional[bool] = None
    quota_notification_threshold: Optional[int] = Field(None, ge=50, le=100)

class AIAnalysisRequest(BaseModel):
    input: str
    conversation_history: Optional[List[AIConversationMessage]] = None

class AIAnalysisResponse(BaseModel):
    analysis: Dict[str, Any]
    questions: List[Dict[str, Any]]
    suggestions: List[str]
    conversation_history: List[AIConversationMessage]
    # Set when the agent autonomously produced a complete quote on this
    # turn — the wizard then jumps straight to the quote instead of
    # asking for customer details.
    quote_id: Optional[int] = None
    quote_number: Optional[str] = None
    pdf_url: Optional[str] = None

class AIFollowUpRequest(BaseModel):
    question: str
    conversation_history: List[AIConversationMessage]

class AIQuestionResponse(BaseModel):
    response: str
    needs_more_info: bool
    conversation_history: List[AIConversationMessage]
    quote_id: Optional[int] = None
    quote_number: Optional[str] = None
    pdf_url: Optional[str] = None

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
    hourly_rate: HourlyRate = None
    material_cost_markup: MaterialCostMarkup = None

class AIQuoteGenerationResponse(BaseModel):
    quote: Dict[str, Any]
    items: List[Dict[str, Any]]
    total_amount: float
    conversation_history: List[AIConversationMessage]
    pdf_url: Optional[str] = None

# Visual Estimate Models (Phase 1 - Multi-modal Vor-Ort-Schätzung)
class VisualEstimateArea(BaseModel):
    wall: Optional[float] = None
    ceiling: Optional[float] = None
    total: Optional[float] = None

class VisualEstimateResponse(BaseModel):
    room_type: str
    estimated_area_sqm: VisualEstimateArea
    area_confidence: str = Field(description="low|medium|high")
    substrate_condition: str
    required_prep_work: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    recommended_material_quality: str
    estimated_labor_hours: float
    summary: str

# Material Price / RAG Models (Phase 2)
class MaterialPriceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=120)
    category: Optional[str] = Field(None, max_length=80, description="e.g. paint, primer, tape, tool")
    unit: str = Field(..., max_length=20, description="m², l, kg, Stk")
    price_net: float = Field(..., ge=0, description="Netto-Preis in EUR")
    region: Optional[str] = Field(None, max_length=20, description="PLZ-Präfix or region tag, e.g. 'DE', 'DE-1'")
    source: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = None

class MaterialPriceCreate(MaterialPriceBase):
    pass

class MaterialPriceUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    price_net: Optional[float] = Field(None, ge=0)
    region: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None

class MaterialPriceResponse(MaterialPriceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MaterialSearchResponse(BaseModel):
    query: str
    results: List[MaterialPriceResponse]
    count: int

# Quick Quote Models (MVP)
class QuickQuoteRequest(BaseModel):
    customer_name: Optional[str] = None
    service_description: str = Field(..., min_length=5, description="Beschreibung der gewünschten Leistung")
    area: Optional[str] = None
    additional_info: Optional[str] = None
    hourly_rate: HourlyRate = None
    material_cost_markup: MaterialCostMarkup = None

class QuickQuoteItemResponse(BaseModel):
    position: int
    description: str
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    category: str

class QuickQuoteResponse(BaseModel):
    quote_id: int
    quote_number: str
    project_title: str
    items: List[QuickQuoteItemResponse]
    subtotal: float
    vat_amount: float
    total_amount: float
    notes: str
    recommendations: List[str]

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
    username: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    hourly_rate: HourlyRate = None
    material_cost_markup: MaterialCostMarkup = None

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
    hourly_rate: Optional[float] = None
    material_cost_markup: Optional[float] = None
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
    is_paid: bool = False
    created_at: datetime
    updated_at: datetime
    created_by_ai: bool
    conversation_history: Optional[List[AIConversationMessage]] = None

    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    id: int
    user_id: int
    quote_id: Optional[int] = None
    amount: float
    currency: str = "EUR"
    status: str
    payment_type: str
    description: Optional[str] = None
    stripe_session_id: Optional[str] = None
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