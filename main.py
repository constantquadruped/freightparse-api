"""
FreightParse API — Turn messy shipping documents into clean structured JSON.
Parses Bills of Lading, freight invoices, and packing lists using Claude.
"""

import anthropic
import io
import json
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import pdfplumber
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Security, Depends, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FreightParse API",
    description="Turn messy shipping documents into clean, structured JSON. "
    "Parses Bills of Lading, freight invoices, and packing lists.",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/demo", include_in_schema=False)
async def demo_page():
    """Serve the upload demo page."""
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

API_KEY_HEADER = APIKeyHeader(name="X-RapidAPI-Proxy-Secret", auto_error=False)
RAPIDAPI_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", "")
INTERNAL_API_KEYS = set(filter(None, os.getenv("API_KEYS", "test-key").split(",")))


async def verify_api_key(
    rapidapi_secret: Optional[str] = Security(API_KEY_HEADER),
    request: Request = None,
):
    # RapidAPI sends proxy secret
    if RAPIDAPI_SECRET and rapidapi_secret == RAPIDAPI_SECRET:
        return "rapidapi"

    # Direct callers use X-API-Key
    direct_key = request.headers.get("X-API-Key", "") if request else ""
    if direct_key in INTERNAL_API_KEYS:
        return "direct"

    raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-key)
# ---------------------------------------------------------------------------

rate_store: dict[str, list[float]] = {}
RATE_LIMIT = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))


def check_rate_limit(key: str):
    now = time.time()
    hits = rate_store.setdefault(key, [])
    hits[:] = [t for t in hits if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per {RATE_WINDOW}s.",
        )
    hits.append(now)


# ---------------------------------------------------------------------------
# Claude client
# ---------------------------------------------------------------------------

@lru_cache()
def get_client() -> anthropic.Anthropic:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=key)


def call_claude(system_prompt: str, user_text: str, max_tokens: int = 2048) -> str:
    try:
        client = get_client()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        message = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514"),
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        return message.content[0].text
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI model error: {e.message}")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

# -- Bill of Lading --

class BOLRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=50000, description="Raw BOL text or OCR output")
    carrier_hint: Optional[str] = Field(None, description="Carrier name hint for better parsing (e.g. 'Maersk', 'MSC')")

class BOLParty(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    contact: Optional[str] = None

class BOLContainer(BaseModel):
    number: Optional[str] = None
    size: Optional[str] = None
    type: Optional[str] = None
    seal_number: Optional[str] = None
    weight_kg: Optional[float] = None

class BOLResponse(BaseModel):
    bol_number: Optional[str] = None
    booking_number: Optional[str] = None
    shipper: Optional[BOLParty] = None
    consignee: Optional[BOLParty] = None
    notify_party: Optional[BOLParty] = None
    carrier: Optional[str] = None
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    place_of_delivery: Optional[str] = None
    date_of_issue: Optional[str] = None
    shipped_on_board_date: Optional[str] = None
    containers: list[BOLContainer] = []
    commodity_description: Optional[str] = None
    gross_weight_kg: Optional[float] = None
    number_of_packages: Optional[int] = None
    package_type: Optional[str] = None
    freight_terms: Optional[str] = None
    hs_codes: list[str] = []
    confidence: float = Field(0.0, description="Parsing confidence 0-1")
    warnings: list[str] = []


# -- Freight Invoice --

class FreightInvoiceRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=50000, description="Raw freight invoice text or OCR output")

class InvoiceLineItem(BaseModel):
    description: str
    charge_type: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    reference: Optional[str] = None

class FreightInvoiceResponse(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    bill_to_name: Optional[str] = None
    bill_to_address: Optional[str] = None
    bol_references: list[str] = []
    container_references: list[str] = []
    po_references: list[str] = []
    line_items: list[InvoiceLineItem] = []
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    payment_terms: Optional[str] = None
    charge_breakdown: Optional[dict] = Field(
        None,
        description="Categorized charges: ocean_freight, fuel_surcharge, "
        "terminal_handling, documentation_fee, detention, demurrage, etc.",
    )
    confidence: float = 0.0
    warnings: list[str] = []


# -- Packing List --

class PackingListRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=50000, description="Raw packing list text or OCR output")

class PackingListItem(BaseModel):
    item_number: Optional[str] = None
    description: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    net_weight_kg: Optional[float] = None
    gross_weight_kg: Optional[float] = None
    dimensions: Optional[str] = None
    hs_code: Optional[str] = None
    country_of_origin: Optional[str] = None
    carton_numbers: Optional[str] = None

class PackingListResponse(BaseModel):
    packing_list_number: Optional[str] = None
    date: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    po_references: list[str] = []
    invoice_references: list[str] = []
    items: list[PackingListItem] = []
    total_packages: Optional[int] = None
    total_gross_weight_kg: Optional[float] = None
    total_net_weight_kg: Optional[float] = None
    total_volume_cbm: Optional[float] = None
    confidence: float = 0.0
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

BOL_SYSTEM_PROMPT = """You are a freight document parsing engine. Extract structured data from Bills of Lading.

Return ONLY valid JSON matching this exact schema (no markdown, no explanation):
{
  "bol_number": "string or null",
  "booking_number": "string or null",
  "shipper": {"name": "string or null", "address": "string or null", "contact": "string or null"},
  "consignee": {"name": "string or null", "address": "string or null", "contact": "string or null"},
  "notify_party": {"name": "string or null", "address": "string or null", "contact": "string or null"},
  "carrier": "string or null",
  "vessel_name": "string or null",
  "voyage_number": "string or null",
  "port_of_loading": "string or null",
  "port_of_discharge": "string or null",
  "place_of_delivery": "string or null",
  "date_of_issue": "YYYY-MM-DD or null",
  "shipped_on_board_date": "YYYY-MM-DD or null",
  "containers": [{"number": "string", "size": "20/40/45", "type": "string", "seal_number": "string or null", "weight_kg": number}],
  "commodity_description": "string or null",
  "gross_weight_kg": number or null,
  "number_of_packages": number or null,
  "package_type": "string or null",
  "freight_terms": "PREPAID/COLLECT/THIRD_PARTY or null",
  "hs_codes": ["string"],
  "confidence": 0.0-1.0,
  "warnings": ["string"]
}

Rules:
- Dates in YYYY-MM-DD format
- Weights in kg (convert from lbs if needed: lbs * 0.453592)
- Container numbers in ISO 6346 format when possible (e.g. MSCU1234567)
- Set confidence based on how complete/clear the source text is
- Add warnings for ambiguous fields, missing critical data, or potential OCR errors
- If a field is not found in the text, set it to null
- Return ONLY the JSON object, nothing else"""

INVOICE_SYSTEM_PROMPT = """You are a freight invoice parsing engine. Extract structured data from freight/shipping invoices.

Return ONLY valid JSON matching this exact schema (no markdown, no explanation):
{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "bill_to_name": "string or null",
  "bill_to_address": "string or null",
  "bol_references": ["string"],
  "container_references": ["string"],
  "po_references": ["string"],
  "line_items": [{"description": "string", "charge_type": "OCEAN_FREIGHT/FUEL_SURCHARGE/THC/DOCUMENTATION/DETENTION/DEMURRAGE/CUSTOMS/INSURANCE/DRAYAGE/OTHER", "amount": number, "currency": "USD/EUR/etc", "reference": "string or null"}],
  "subtotal": number or null,
  "tax": number or null,
  "total": number or null,
  "currency": "USD/EUR/etc or null",
  "payment_terms": "string or null",
  "charge_breakdown": {"ocean_freight": number, "fuel_surcharge": number, "terminal_handling": number, "documentation_fee": number, "detention": number, "demurrage": number, "customs_clearance": number, "insurance": number, "drayage": number, "other": number},
  "confidence": 0.0-1.0,
  "warnings": ["string"]
}

Rules:
- Categorize each line item into the correct charge_type
- charge_breakdown should sum charges by category (only include categories that appear)
- Dates in YYYY-MM-DD format
- Amounts as numbers (not strings)
- If currency symbol is $ assume USD unless context says otherwise
- Set confidence based on completeness
- Add warnings for calculation mismatches, unclear charges, or missing data
- Return ONLY the JSON object, nothing else"""

PACKING_LIST_SYSTEM_PROMPT = """You are a freight document parsing engine. Extract structured data from packing lists.

Return ONLY valid JSON matching this exact schema (no markdown, no explanation):
{
  "packing_list_number": "string or null",
  "date": "YYYY-MM-DD or null",
  "shipper": "string or null",
  "consignee": "string or null",
  "po_references": ["string"],
  "invoice_references": ["string"],
  "items": [{"item_number": "string or null", "description": "string", "quantity": number, "unit": "PCS/KG/LBS/CTN/PLT/etc", "net_weight_kg": number or null, "gross_weight_kg": number or null, "dimensions": "LxWxH cm or null", "hs_code": "string or null", "country_of_origin": "2-letter ISO code or null", "carton_numbers": "string or null"}],
  "total_packages": number or null,
  "total_gross_weight_kg": number or null,
  "total_net_weight_kg": number or null,
  "total_volume_cbm": number or null,
  "confidence": 0.0-1.0,
  "warnings": ["string"]
}

Rules:
- Weights in kg (convert from lbs if needed: lbs * 0.453592)
- Dimensions in cm (convert from inches if needed: inches * 2.54)
- Volume in CBM (cubic meters)
- HS codes should be 6-10 digits
- Country of origin as 2-letter ISO code (CN, US, DE, etc.)
- Set confidence based on completeness
- Add warnings for weight mismatches, missing HS codes, unclear items
- Return ONLY the JSON object, nothing else"""


# ---------------------------------------------------------------------------
# File extraction helper
# ---------------------------------------------------------------------------

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def extract_text_from_upload(file: UploadFile) -> str:
    """Extract text from an uploaded file (PDF, image, or plain text)."""
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 10 MB.")

    content_type = file.content_type or ""
    filename = (file.filename or "").lower()

    # Plain text files
    if content_type.startswith("text/") or filename.endswith(".txt"):
        return content.decode("utf-8", errors="replace")

    # PDF files
    if content_type == "application/pdf" or filename.endswith(".pdf"):
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                    # Also extract tables as text
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            row_text = " | ".join(
                                str(cell) if cell else "" for cell in row
                            )
                            pages.append(row_text)
                extracted = "\n".join(pages)
                if not extracted.strip():
                    raise HTTPException(
                        status_code=422,
                        detail="Could not extract text from PDF. The file may be image-only. "
                        "Try using an OCR tool first, then submit the text.",
                    )
                return extracted
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to read PDF: {str(e)}")

    # Images — use Claude's vision capability
    if content_type.startswith("image/"):
        import base64

        b64 = base64.b64encode(content).decode("utf-8")
        media_type = content_type
        if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            media_type = "image/png"  # fallback

        try:
            client = get_client()
            message = client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514"),
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "Extract ALL text from this shipping document image. "
                                "Include every detail: numbers, addresses, weights, "
                                "dimensions, dates, reference numbers, table data. "
                                "Return the raw text only, no commentary.",
                            },
                        ],
                    }
                ],
            )
            return message.content[0].text
        except anthropic.APIError as e:
            raise HTTPException(status_code=502, detail=f"Vision extraction error: {e.message}")

    raise HTTPException(
        status_code=415,
        detail=f"Unsupported file type: {content_type}. "
        "Supported: PDF, PNG, JPEG, WebP, GIF, plain text.",
    )


# ---------------------------------------------------------------------------
# Parsing helper
# ---------------------------------------------------------------------------

def parse_document(system_prompt: str, text: str, carrier_hint: str = None) -> dict:
    """Send text to Claude and parse the JSON response."""
    user_msg = text
    if carrier_hint:
        user_msg = f"[Carrier hint: {carrier_hint}]\n\n{text}"

    raw = call_claude(system_prompt, user_msg)

    # Strip markdown fences if Claude adds them despite instructions
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end])
        raise HTTPException(
            status_code=502,
            detail="Failed to parse structured response from AI model",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "FreightParse API",
        "version": "1.1.0",
        "endpoints": [
            {"path": "/parse-bol", "method": "POST", "description": "Parse Bill of Lading (text)"},
            {"path": "/parse-freight-invoice", "method": "POST", "description": "Parse freight invoice (text)"},
            {"path": "/parse-packing-list", "method": "POST", "description": "Parse packing list (text)"},
            {"path": "/parse-bol/upload", "method": "POST", "description": "Parse Bill of Lading (file upload: PDF/image/text)"},
            {"path": "/parse-freight-invoice/upload", "method": "POST", "description": "Parse freight invoice (file upload: PDF/image/text)"},
            {"path": "/parse-packing-list/upload", "method": "POST", "description": "Parse packing list (file upload: PDF/image/text)"},
        ],
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/parse-bol", response_model=BOLResponse)
async def parse_bol(req: BOLRequest, auth: str = Depends(verify_api_key)):
    check_rate_limit(auth)
    data = parse_document(BOL_SYSTEM_PROMPT, req.text, req.carrier_hint)
    return BOLResponse(**data)


@app.post("/parse-freight-invoice", response_model=FreightInvoiceResponse)
async def parse_freight_invoice(req: FreightInvoiceRequest, auth: str = Depends(verify_api_key)):
    check_rate_limit(auth)
    data = parse_document(INVOICE_SYSTEM_PROMPT, req.text)
    return FreightInvoiceResponse(**data)


@app.post("/parse-packing-list", response_model=PackingListResponse)
async def parse_packing_list(req: PackingListRequest, auth: str = Depends(verify_api_key)):
    check_rate_limit(auth)
    data = parse_document(PACKING_LIST_SYSTEM_PROMPT, req.text)
    return PackingListResponse(**data)


# ---------------------------------------------------------------------------
# File upload endpoints
# ---------------------------------------------------------------------------

@app.post("/parse-bol/upload", response_model=BOLResponse)
async def parse_bol_upload(
    file: UploadFile = File(..., description="PDF, image, or text file of a Bill of Lading"),
    carrier_hint: Optional[str] = Form(None, description="Carrier name hint"),
    auth: str = Depends(verify_api_key),
):
    """Parse a Bill of Lading from an uploaded file (PDF, image, or text)."""
    check_rate_limit(auth)
    text = await extract_text_from_upload(file)
    data = parse_document(BOL_SYSTEM_PROMPT, text, carrier_hint)
    return BOLResponse(**data)


@app.post("/parse-freight-invoice/upload", response_model=FreightInvoiceResponse)
async def parse_freight_invoice_upload(
    file: UploadFile = File(..., description="PDF, image, or text file of a freight invoice"),
    auth: str = Depends(verify_api_key),
):
    """Parse a freight invoice from an uploaded file (PDF, image, or text)."""
    check_rate_limit(auth)
    text = await extract_text_from_upload(file)
    data = parse_document(INVOICE_SYSTEM_PROMPT, text)
    return FreightInvoiceResponse(**data)


@app.post("/parse-packing-list/upload", response_model=PackingListResponse)
async def parse_packing_list_upload(
    file: UploadFile = File(..., description="PDF, image, or text file of a packing list"),
    auth: str = Depends(verify_api_key),
):
    """Parse a packing list from an uploaded file (PDF, image, or text)."""
    check_rate_limit(auth)
    text = await extract_text_from_upload(file)
    data = parse_document(PACKING_LIST_SYSTEM_PROMPT, text)
    return PackingListResponse(**data)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
