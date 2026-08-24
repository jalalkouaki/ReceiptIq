from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # 'admin' or 'user'
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False)

    receipts = relationship("Receipt", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="user", cascade="all, delete-orphan")
    price_histories = relationship("PriceHistory", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "must_change_password": self.must_change_password
        }


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    tax_deductible = Column(Boolean, default=True)
    color = Column(String(20), default="#6c757d")

    receipts = relationship("Receipt", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "tax_deductible": self.tax_deductible,
            "color": self.color
        }


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    vendor = Column(String(200), nullable=True)
    receipt_date = Column(String(20), nullable=True)
    total_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    payment_method = Column(String(50), nullable=True)
    category_id = Column(Integer, ForeignKey("expense_categories.id"), nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    status = Column(String(20), default="pending")  # 'pending', 'completed', 'needs_review'
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="receipts")
    category = relationship("ExpenseCategory", back_populates="receipts")
    warranty_items = relationship("WarrantyItem", back_populates="receipt", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="receipt")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "file_path": self.file_path,
            "vendor": self.vendor or "Unknown",
            "receipt_date": self.receipt_date,
            "total_amount": self.total_amount,
            "tax_amount": self.tax_amount,
            "currency": self.currency,
            "payment_method": self.payment_method or "Cash/Card",
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "Uncategorized",
            "category_color": self.category.color if self.category else "#6c757d",
            "raw_ocr_text": self.raw_ocr_text or "",
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class WarrantyItem(Base):
    __tablename__ = "warranty_items"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True)
    item_name = Column(String(200), nullable=False)
    purchase_date = Column(String(20), nullable=False)
    warranty_months = Column(Integer, default=12)
    return_deadline = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)

    receipt = relationship("Receipt", back_populates="warranty_items")

    def to_dict(self):
        return {
            "id": self.id,
            "receipt_id": self.receipt_id,
            "item_name": self.item_name,
            "purchase_date": self.purchase_date,
            "warranty_months": self.warranty_months,
            "return_deadline": self.return_deadline,
            "notes": self.notes or ""
        }


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vendor = Column(String(200), nullable=False)
    amount = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    frequency = Column(String(20), default="monthly")  # 'monthly', 'quarterly', 'yearly'
    next_renewal = Column(String(20), nullable=True)
    active = Column(Boolean, default=True)

    user = relationship("User", back_populates="subscriptions")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "vendor": self.vendor,
            "amount": self.amount,
            "currency": self.currency,
            "frequency": self.frequency,
            "next_renewal": self.next_renewal,
            "active": self.active
        }


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True)
    name = Column(String(200), nullable=False)
    quantity = Column(Integer, default=1)
    unit_cost = Column(Float, default=0.0)
    reorder_point = Column(Integer, default=1)

    user = relationship("User", back_populates="inventory_items")
    receipt = relationship("Receipt", back_populates="inventory_items")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "receipt_id": self.receipt_id,
            "name": self.name,
            "quantity": self.quantity,
            "unit_cost": self.unit_cost,
            "reorder_point": self.reorder_point
        }


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vendor = Column(String(200), nullable=False)
    item_name = Column(String(200), nullable=False)
    price = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    date = Column(String(20), nullable=False)

    user = relationship("User", back_populates="price_histories")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "vendor": self.vendor,
            "item_name": self.item_name,
            "price": self.price,
            "currency": self.currency,
            "date": self.date
        }


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value
        }
