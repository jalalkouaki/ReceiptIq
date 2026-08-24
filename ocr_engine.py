import os
import re
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
from config import load_settings
from logger import log_event

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYTESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:  # pragma: no cover
    PDF2IMAGE_AVAILABLE = False

# Keyword map for rule-based categorization
CATEGORY_KEYWORDS = {
    "meals": ["meals", "restaurant", "cafe", "coffee", "starbucks", "diner", "bistro", "doordash", "ubereats", "mcdonald", "subway", "pizza", "burger", "grill"],
    "software-subscriptions": ["software", "saas", "hosting", "domain", "subscription", "github", "aws", "digitalocean", "adobe", "microsoft", "google cloud", "slack", "zoom", "jetbrains", "cloudflare", "spotify", "netflix"],
    "travel": ["travel", "airfare", "hotel", "taxi", "uber", "lyft", "train", "flight", "delta", "united", "american airlines", "airbnb", "booking", "expedia", "hertz", "enterprise"],
    "office-supplies": ["office", "supplies", "staples", "amazon basics", "paper", "desk", "chair", "office depot", "pens", "toner", "ink", "stationery"],
    "utilities": ["phone", "internet", "utility", "electricity", "water", "gas", "verizon", "at&t", "t-mobile", "comcast", "spectrum", "electric", "power"],
    "marketing": ["marketing", "ads", "facebook", "google ads", "instagram", "linkedin", "twitter", "meta", "mailchimp", "advertising", "promo"],
    "groceries": ["groceries", "supermarket", "food", "walmart", "trader joe", "whole foods", "target", "kroger", "safeway", "costco", "aldi", "publix"],
}

ELECTRONICS_KEYWORDS = [
    "laptop", "phone", "tv", "monitor", "headphone", "computer", "camera", "dell", "hp", "lenovo",
    "apple", "samsung", "sony", "best buy", "micro center", "appliance", "refrigerator", "microwave",
    "tablet", "macbook", "ipad", "iphone", "gpu", "processor", "electronics"
]


def preprocess_image(image_path: str) -> Image.Image:
    """Preprocess image for better OCR quality (grayscale, contrast, threshold)."""
    img = Image.open(image_path)
    # Convert to grayscale
    img = img.convert("L")
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    # Filter noise
    img = img.filter(ImageFilter.SHARPEN)
    return img


def convert_pdf_to_images(pdf_path: str) -> list[Image.Image]:
    """Convert PDF file to PIL Images using pdf2image."""
    if not PDF2IMAGE_AVAILABLE:
        log_event("error", "pdf2image library is not installed", level="ERROR")
        raise RuntimeError("PDF processing requires pdf2image and Poppler installed.")
    
    cfg = load_settings()
    poppler_path = os.environ.get("POPPLER_PATH")
    
    try:
        if poppler_path:
            return convert_from_path(pdf_path, poppler_path=poppler_path)
        return convert_from_path(pdf_path)
    except Exception as e:
        log_event("error", f"PDF conversion failed for {pdf_path}: {e}", level="ERROR")
        raise e


def run_ocr(file_path: str, ocr_lang: str = "eng") -> str:
    """Extract raw text from receipt image or PDF file using Tesseract."""
    if not PYTESSERACT_AVAILABLE:
        log_event("ocr", "pytesseract library not available", level="WARNING")
        return ""

    tesseract_cmd = os.environ.get("TESSERACT_PATH")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    ext = Path(file_path).suffix.lower()
    raw_text = ""

    try:
        if ext == ".pdf":
            images = convert_pdf_to_images(file_path)
            text_parts = []
            for img in images:
                processed = img.convert("L")
                text_parts.append(pytesseract.image_to_string(processed, lang=ocr_lang))
            raw_text = "\n\n".join(text_parts)
        else:
            processed_img = preprocess_image(file_path)
            raw_text = pytesseract.image_to_string(processed_img, lang=ocr_lang)

        log_event("ocr", f"OCR successful for {file_path} (extracted {len(raw_text)} chars)", level="INFO")
    except Exception as e:
        log_event("ocr", f"OCR failed for {file_path}: {e}", level="ERROR")

    return raw_text.strip()


def parse_vendor(text: str) -> str:
    """Extract vendor name from raw receipt text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Unknown Vendor"

    ignore_words = {"receipt", "tax invoice", "welcome", "thank you", "tel:", "phone:", "date:", "cashier", "total", "subtotal", "order", "invoice"}
    
    for line in lines[:5]:
        clean = line.strip()
        if len(clean) > 2 and not any(w in clean.lower() for w in ignore_words) and not re.match(r"^[\d\W]+$", clean):
            return clean[:100]

    return lines[0][:100] if lines else "Unknown Vendor"


def parse_date(text: str) -> str:
    """Extract purchase date from text and format as YYYY-MM-DD."""
    # Match YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, MMM DD, YYYY
    date_patterns = [
        (r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b", "YMD"),
        (r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(0[1-9]|[12]\d|3[01])[\s,]+(20\d{2})\b", "STR"),
        (r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](20\d{2})\b", "MDY"),
        (r"\b(0[1-9]|[12]\d|3[01])[-/](0[1-9]|1[0-2])[-/](20\d{2})\b", "DMY")
    ]

    for pattern, ptype in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if ptype == "YMD":
                return f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
            elif ptype == "STR":
                month_str, day, year = groups[0][:3].title(), int(groups[1]), int(groups[2])
                try:
                    dt = datetime.strptime(f"{month_str} {day} {year}", "%b %d %Y")
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass
            elif ptype == "MDY":
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                return f"{year:04d}-{month:02d}-{day:02d}"
            elif ptype == "DMY":
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                return f"{year:04d}-{month:02d}-{day:02d}"

    # Default to today's date if date not clearly detected
    return datetime.utcnow().strftime("%Y-%m-%d")


def parse_amounts(text: str) -> tuple[float, float, str]:
    """Extract total amount, tax amount, and currency from receipt text."""
    currency = "USD"
    if "€" in text or "EUR" in text:
        currency = "EUR"
    elif "£" in text or "GBP" in text:
        currency = "GBP"
    elif "CAD" in text or "C$" in text:
        currency = "CAD"
    elif "AUD" in text or "A$" in text:
        currency = "AUD"

    lines = text.splitlines()
    total_amount = 0.0
    tax_amount = 0.0

    total_patterns = [
        r"(?:grand\s+total|total\s+due|net\s+total|amount\s+due)\s*[:\$€£]?(?:\s*(?:CAD|AUD|C\$|A\$))?\s*([\d,]+\.\d{2})\b",
        r"(?<!sub)\btotal\b\s*:\s*[\$€£]?(?:\s*(?:CAD|AUD|C\$|A\$))?\s*([\d,]+\.\d{2})\b",
        r"(?<!sub)\btotal\b\s*[\$€£]?(?:\s*(?:CAD|AUD|C\$|A\$))?\s*([\d,]+\.\d{2})\b",
        r"([\d,]+\.\d{2})\s*(?:€|EUR)\b",
        r"[\$€£]\s*([\d,]+\.\d{2})\b"
    ]

    for pattern in total_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            amounts = []
            for m in matches:
                try:
                    val = float(m.replace(",", ""))
                    amounts.append(val)
                except ValueError:
                    continue
            if amounts:
                total_amount = max(amounts)
                break

    tax_patterns = [
        r"(?:tax|vat|tva|gst|hst|pst)\s*[:\$€£]?\s*([\d,]+\.\d{2})\b",
        r"(?:tax|vat|tva|gst|hst|pst)\s*:\s*[\$€£]?\s*([\d,]+\.\d{2})\b",
        r"([\d,]+\.\d{2})\s*(?:€|EUR)?\s*(?:tva|vat|tax)\b"
    ]

    for pattern in tax_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                tax_amount = float(match.group(1).replace(",", ""))
                break
            except ValueError:
                pass

    return total_amount, tax_amount, currency


def parse_payment_method(text: str) -> str:
    """Extract payment method (Visa, Mastercard, Cash, etc.)."""
    upper = text.upper()
    if "VISA" in upper:
        return "Visa"
    if "MASTERCARD" in upper or "MASTER CARD" in upper or "MC" in upper:
        return "Mastercard"
    if "AMEX" in upper or "AMERICAN EXPRESS" in upper:
        return "Amex"
    if "DEBIT" in upper:
        return "Debit Card"
    if "CASH" in upper:
        return "Cash"
    if "PAYPAL" in upper:
        return "PayPal"
    if "APPLE PAY" in upper:
        return "Apple Pay"
    return "Credit Card"


def classify_category(text: str, vendor: str) -> str:
    """Classify expense category based on rule-based keywords in text and vendor."""
    combined = f"{vendor} {text}".lower()

    for category_slug, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined):
                return category_slug

    return "other"


def calculate_confidence(vendor: str, date_str: str, total: float, category_slug: str) -> float:
    """Calculate confidence score (0.0 to 1.0) based on extracted fields."""
    score = 0.0
    if vendor and vendor != "Unknown Vendor":
        score += 0.3
    if total > 0:
        score += 0.3
    if date_str:
        score += 0.2
    if category_slug != "other":
        score += 0.2
    return min(1.0, round(score, 2))


def process_receipt_file(file_path: str, ocr_lang: str = "eng") -> dict:
    """Full OCR and extraction pipeline for a receipt file."""
    raw_text = run_ocr(file_path, ocr_lang=ocr_lang)
    vendor = parse_vendor(raw_text)
    receipt_date = parse_date(raw_text)
    total_amount, tax_amount, currency = parse_amounts(raw_text)
    payment_method = parse_payment_method(raw_text)
    category_slug = classify_category(raw_text, vendor)
    confidence = calculate_confidence(vendor, receipt_date, total_amount, category_slug)
    
    status = "needs_review" if confidence < 0.8 else "completed"

    return {
        "vendor": vendor,
        "receipt_date": receipt_date,
        "total_amount": total_amount,
        "tax_amount": tax_amount,
        "currency": currency,
        "payment_method": payment_method,
        "category_slug": category_slug,
        "raw_ocr_text": raw_text,
        "confidence": confidence,
        "status": status,
        "is_electronics": is_electronics_receipt(raw_text, category_slug, vendor)
    }


def is_electronics_receipt(raw_text: str, category_slug: str, vendor: str) -> bool:
    """Check if receipt is for electronics or appliances."""
    combined = f"{vendor} {raw_text}".lower()
    return any(kw in combined for kw in ELECTRONICS_KEYWORDS)
