"""
FreightParse API — Test script with realistic freight document samples.
Run: python test_api.py
Requires the API running on localhost:8000.
"""

import httpx
import json
import sys

BASE = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json", "X-API-Key": "test-key"}


# ---------------------------------------------------------------------------
# Sample documents (realistic freight text)
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
Contact: Sarah Mitchell  Tel: +1-562-555-0147

NOTIFY PARTY:
Same as consignee

CARRIER: Mediterranean Shipping Company (MSC)
VESSEL: MSC ISABELLA   VOYAGE: FE428W
PORT OF LOADING: Nansha, China (CNNSA)
PORT OF DISCHARGE: Long Beach, USA (USLGB)
PLACE OF DELIVERY: Long Beach, CA

DATE OF ISSUE: January 15, 2026
SHIPPED ON BOARD DATE: January 18, 2026

CONTAINER DETAILS:
Container No: MSCU7834521  Size: 40HC  Seal: CN2847391  Weight: 18,450 kg
Container No: MSCU9912847  Size: 40HC  Seal: CN2847392  Weight: 21,200 kg

COMMODITY: Electronic Consumer Goods - LED Monitors and Accessories
HS CODE: 8528.52, 8528.59
TOTAL PACKAGES: 1,240 cartons
GROSS WEIGHT: 39,650 KGS
MEASUREMENT: 128.4 CBM

FREIGHT: PREPAID

SHIPPED ON BOARD in apparent good order and condition.
"""

SAMPLE_INVOICE = """
FREIGHT INVOICE

APEX OCEAN FREIGHT SERVICES LLC
1200 Port Authority Drive, Suite 850
Newark, NJ 07114
Tax ID: 82-4917305

INVOICE NO: APX-2026-00847
INVOICE DATE: February 1, 2026
DUE DATE: March 3, 2026
PAYMENT TERMS: Net 30

BILL TO:
Pacific Coast Distributors Inc.
2847 Harbor Blvd, Suite 400
Long Beach, CA 90802

SHIPMENT REFERENCES:
B/L: MEDU4712839
Container: MSCU7834521, MSCU9912847
PO#: PCO-2026-1147, PCO-2026-1148

CHARGES:
Description                          Amount (USD)
----------------------------------------------------
Ocean Freight (Nansha-Long Beach)    $4,200.00
  40HC x 2 @ $2,100 each
Bunker Adjustment Factor (BAF)         $680.00
Low Sulphur Surcharge (LSS)            $320.00
Terminal Handling - Origin (THC)        $370.00
Terminal Handling - Dest (THC)          $450.00
Documentation Fee                       $75.00
Bill of Lading Fee                      $50.00
AMS Filing Fee                          $35.00
Customs Clearance                      $275.00
ISF Filing (10+2)                       $50.00
Chassis Usage (3 days)                 $225.00
Drayage - Port to Warehouse            $850.00
Fuel Surcharge (Drayage)               $127.50
----------------------------------------------------
SUBTOTAL:                            $7,707.50
TAX:                                     $0.00
TOTAL DUE:                           $7,707.50

Wire Transfer:
Bank: JPMorgan Chase
Account: 8291047350
Routing: 021000021
"""

SAMPLE_PACKING_LIST = """
PACKING LIST

Packing List No: PL-GZ-2026-0471
Date: January 12, 2026

FROM:
Guangzhou Sunrise Electronics Co., Ltd
No. 188 Huangpu East Road, Guangzhou

TO:
Pacific Coast Distributors Inc.
2847 Harbor Blvd, Long Beach, CA 90802

PO Reference: PCO-2026-1147, PCO-2026-1148
Invoice Ref: GZ-INV-2026-0892

ITEM DETAILS:

No.  Description                    Qty    Unit   N.W.(kg)  G.W.(kg)  Dimensions(cm)  HS Code     Origin  Cartons
---  ----------------------------  -----  -----  --------  --------  --------------  ----------  ------  --------
1    27" LED Monitor Model X270    500    PCS    4,500.0   5,250.0   72x45x18        8528.5200   CN      500
2    32" LED Monitor Model X320    300    PCS    3,600.0   4,200.0   82x52x20        8528.5200   CN      300
3    Monitor Stand Adj. MS-100     400    PCS    1,200.0   1,440.0   45x35x15        8529.9090   CN      200
4    HDMI Cable 2m HC-200          2000   PCS      400.0     480.0   25x5x3          8544.4200   CN      100
5    Power Adapter PA-65W          800    PCS      640.0     768.0   12x8x6          8504.4090   CN      80
6    User Manual + Warranty Card   800    PCS      120.0     144.0   30x21x2         4901.9900   CN      60

TOTALS:
Total Packages: 1,240 cartons
Total Net Weight: 10,460.0 kg
Total Gross Weight: 12,282.0 kg
Total Volume: 128.4 CBM
"""


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def test_endpoint(name: str, path: str, payload: dict):
    print(f"\n{'='*60}")
    print(f"  Testing: {name}")
    print(f"  POST {BASE}{path}")
    print(f"{'='*60}")

    try:
        resp = httpx.post(f"{BASE}{path}", json=payload, headers=HEADERS, timeout=60)
    except httpx.ConnectError:
        print("  ERROR: Cannot connect. Is the API running on localhost:8000?")
        return False

    print(f"  Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  Response ({len(json.dumps(data))} bytes):")
        print(json.dumps(data, indent=2, default=str)[:3000])
        if "confidence" in data:
            print(f"\n  Confidence: {data['confidence']}")
        if data.get("warnings"):
            print(f"  Warnings: {data['warnings']}")
        return True
    else:
        print(f"  Error: {resp.text[:500]}")
        return False


def main():
    print("FreightParse API Test Suite")
    print("=" * 60)

    # Health check
    try:
        resp = httpx.get(f"{BASE}/health", timeout=5)
        print(f"Health check: {resp.json()}")
    except httpx.ConnectError:
        print("ERROR: API not running. Start with: python main.py")
        sys.exit(1)

    results = []

    results.append(test_endpoint(
        "Bill of Lading Parser",
        "/parse-bol",
        {"text": SAMPLE_BOL, "carrier_hint": "MSC"},
    ))

    results.append(test_endpoint(
        "Freight Invoice Parser",
        "/parse-freight-invoice",
        {"text": SAMPLE_INVOICE},
    ))

    results.append(test_endpoint(
        "Packing List Parser",
        "/parse-packing-list",
        {"text": SAMPLE_PACKING_LIST},
    ))

    # Summary
    print(f"\n{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"  Results: {passed}/{total} passed")
    if passed == total:
        print("  All tests passed!")
    else:
        print("  Some tests failed.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
