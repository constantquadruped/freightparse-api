"""Shared fixtures for FreightParse tests."""

import json
import os
import pytest
from unittest.mock import AsyncMock, patch

# Set test env vars before importing app
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-for-testing")
os.environ.setdefault("API_KEYS", "test-key-1,test-key-2")

from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-key-1", "Content-Type": "application/json"}


@pytest.fixture
def rapidapi_headers():
    os.environ["RAPIDAPI_PROXY_SECRET"] = "rapid-secret-123"
    return {
        "X-RapidAPI-Proxy-Secret": "rapid-secret-123",
        "Content-Type": "application/json",
    }


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Sample documents
# ---------------------------------------------------------------------------

SAMPLE_BOL = """
BILL OF LADING
B/L No: MEDU4712839
Booking No: 2174839201

SHIPPER:
Guangzhou Sunrise Electronics Co., Ltd
No. 188 Huangpu East Road, Guangzhou, Guangdong 510700, China
Contact: Mr. Wang Wei  Tel: +86-20-8765-4321

CONSIGNEE:
Pacific Coast Distributors Inc.
2847 Harbor Blvd, Suite 400
Long Beach, CA 90802, USA

CARRIER: Mediterranean Shipping Company (MSC)
VESSEL: MSC ISABELLA   VOYAGE: FE428W
PORT OF LOADING: Nansha, China (CNNSA)
PORT OF DISCHARGE: Long Beach, USA (USLGB)

DATE OF ISSUE: January 15, 2026

CONTAINER DETAILS:
Container No: MSCU7834521  Size: 40HC  Seal: CN2847391  Weight: 18,450 kg

COMMODITY: Electronic Consumer Goods - LED Monitors
HS CODE: 8528.52
TOTAL PACKAGES: 1,240 cartons
GROSS WEIGHT: 39,650 KGS
FREIGHT: PREPAID
"""

SAMPLE_INVOICE = """
FREIGHT INVOICE
INVOICE NO: APX-2026-00847
INVOICE DATE: February 1, 2026
DUE DATE: March 3, 2026

BILL TO:
Pacific Coast Distributors Inc.
2847 Harbor Blvd, Suite 400, Long Beach, CA 90802

CHARGES:
Ocean Freight (Nansha-Long Beach)    $4,200.00
Bunker Adjustment Factor (BAF)         $680.00
Terminal Handling - Origin (THC)        $370.00
Documentation Fee                       $75.00
TOTAL DUE:                           $5,325.00
"""

SAMPLE_PACKING_LIST = """
PACKING LIST
Packing List No: PL-GZ-2026-0471
Date: January 12, 2026

FROM: Guangzhou Sunrise Electronics Co., Ltd
TO: Pacific Coast Distributors Inc.

ITEMS:
1    27" LED Monitor Model X270    500 PCS    5,250.0 kg    8528.5200   CN
2    Monitor Stand MS-100          400 PCS    1,440.0 kg    8529.9090   CN

Total Packages: 700 cartons
Total Gross Weight: 6,690.0 kg
"""

# Pre-built Claude responses for mocking
MOCK_BOL_RESPONSE = json.dumps({
    "bol_number": "MEDU4712839",
    "booking_number": "2174839201",
    "shipper": {"name": "Guangzhou Sunrise Electronics Co., Ltd",
                "address": "No. 188 Huangpu East Road, Guangzhou, Guangdong 510700, China",
                "contact": "Mr. Wang Wei +86-20-8765-4321"},
    "consignee": {"name": "Pacific Coast Distributors Inc.",
                  "address": "2847 Harbor Blvd, Suite 400, Long Beach, CA 90802, USA",
                  "contact": None},
    "notify_party": None,
    "carrier": "Mediterranean Shipping Company (MSC)",
    "vessel_name": "MSC ISABELLA",
    "voyage_number": "FE428W",
    "port_of_loading": "Nansha, China",
    "port_of_discharge": "Long Beach, USA",
    "place_of_delivery": None,
    "date_of_issue": "2026-01-15",
    "shipped_on_board_date": None,
    "containers": [{"number": "MSCU7834521", "size": "40HC", "type": None,
                    "seal_number": "CN2847391", "weight_kg": 18450.0}],
    "commodity_description": "Electronic Consumer Goods - LED Monitors",
    "gross_weight_kg": 39650.0,
    "number_of_packages": 1240,
    "package_type": "cartons",
    "freight_terms": "PREPAID",
    "hs_codes": ["8528.52"],
    "confidence": 0.92,
    "warnings": []
})

MOCK_INVOICE_RESPONSE = json.dumps({
    "invoice_number": "APX-2026-00847",
    "invoice_date": "2026-02-01",
    "due_date": "2026-03-03",
    "vendor_name": None,
    "vendor_address": None,
    "bill_to_name": "Pacific Coast Distributors Inc.",
    "bill_to_address": "2847 Harbor Blvd, Suite 400, Long Beach, CA 90802",
    "bol_references": [],
    "container_references": [],
    "po_references": [],
    "line_items": [
        {"description": "Ocean Freight", "charge_type": "OCEAN_FREIGHT", "amount": 4200.0, "currency": "USD", "reference": None},
        {"description": "Bunker Adjustment Factor", "charge_type": "FUEL_SURCHARGE", "amount": 680.0, "currency": "USD", "reference": None},
    ],
    "subtotal": 5325.0,
    "tax": 0.0,
    "total": 5325.0,
    "currency": "USD",
    "payment_terms": None,
    "charge_breakdown": {"ocean_freight": 4200.0, "fuel_surcharge": 680.0, "terminal_handling": 370.0, "documentation_fee": 75.0},
    "confidence": 0.88,
    "warnings": []
})

MOCK_PACKING_RESPONSE = json.dumps({
    "packing_list_number": "PL-GZ-2026-0471",
    "date": "2026-01-12",
    "shipper": "Guangzhou Sunrise Electronics Co., Ltd",
    "consignee": "Pacific Coast Distributors Inc.",
    "po_references": [],
    "invoice_references": [],
    "items": [
        {"item_number": "1", "description": "27\" LED Monitor Model X270", "quantity": 500, "unit": "PCS",
         "net_weight_kg": None, "gross_weight_kg": 5250.0, "dimensions": None, "hs_code": "8528.5200",
         "country_of_origin": "CN", "carton_numbers": None},
    ],
    "total_packages": 700,
    "total_gross_weight_kg": 6690.0,
    "total_net_weight_kg": None,
    "total_volume_cbm": None,
    "confidence": 0.85,
    "warnings": []
})

