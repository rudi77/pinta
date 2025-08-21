from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile information
    company_name = Column(String(100))
    phone = Column(String(20))
    address = Column(Text)
    
    # Subscription and quota
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime)
    quotes_this_month = Column(Integer, default=0)
    additional_quotes = Column(Integer, default=0)
    
    # Stripe integration
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    
    # Account status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    quotes = relationship("Quote", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_number = Column(String(50), unique=True, index=True, nullable=False)
    
    # User reference
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Customer information
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(100))
    customer_phone = Column(String(20))
    customer_address = Column(Text)
    
    # Project information
    project_title = Column(String(200), nullable=False)
    project_description = Column(Text)
    
    # Pricing
    total_amount = Column(Float)
    labor_hours = Column(Float)
    hourly_rate = Column(Float)
    material_cost = Column(Float)
    additional_costs = Column(Float)
    
    # Status and processing
    status = Column(String(20), default="draft")  # draft, completed, sent, accepted, rejected
    ai_processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    
    # AI and conversation
    created_by_ai = Column(Boolean, default=False)  # Whether this quote was created via AI chat
    conversation_history = Column(Text, nullable=True)  # JSON string of conversation history
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="quotes")
    quote_items = relationship("QuoteItem", back_populates="quote", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="quote")

class QuoteItem(Base):
    __tablename__ = "quote_items"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    
    position = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    # Additional information
    room_name = Column(String(100))
    area_sqm = Column(Float)
    work_type = Column(String(50))  # painting, priming, etc.
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    quote = relationship("Quote", back_populates="quote_items")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quote_id = Column(Integer, ForeignKey("quotes.id"))
    
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # OCR and analysis results
    extracted_text = Column(Text)
    analysis_result = Column(Text, nullable=True)  # JSON string
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="documents")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=True)
    
    # Stripe information
    stripe_payment_intent_id = Column(String(200), unique=True)
    stripe_session_id = Column(String(200), unique=True)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR")
    status = Column(String(50), nullable=False)  # pending, completed, failed, refunded
    
    payment_type = Column(String(50), nullable=False)  # premium_upgrade, additional_quotes
    description = Column(String(200))
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="payments")
    quote = relationship("Quote", back_populates="payments")

