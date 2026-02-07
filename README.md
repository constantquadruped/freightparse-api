# FreightParse API

**Turn messy shipping documents into clean, structured JSON.**

Parses Bills of Lading, freight invoices, and packing lists. Built for freight forwarders, logistics platforms, and supply chain software.

## Endpoints

| Endpoint | Input | Output | Price |
|----------|-------|--------|-------|
| `POST /parse-bol` | Bill of Lading text | Shipper, consignee, containers, ports, weights, HS codes | $0.15/doc |
| `POST /parse-freight-invoice` | Freight invoice text | Charges breakdown, line items, references, totals | $0.15/doc |
| `POST /parse-packing-list` | Packing list text | Items, quantities, weights, dimensions, HS codes | $0.10/doc |

## Quick Start

### Local Development

```bash
cd freightparse-api
pip install -r requirements.txt

# Set API key
set ANTHROPIC_API_KEY=sk-ant-xxxxx   # Windows
export ANTHROPIC_API_KEY=sk-ant-xxxxx # Linux/Mac

# Run
python main.py
```

Open http://localhost:8000/docs for interactive API docs.

### Test

```bash
python test_api.py
```

## Example: Parse a Bill of Lading

```bash
curl -X POST http://localhost:8000/parse-bol \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "text": "BILL OF LADING\nB/L No: MEDU4712839\nSHIPPER: Guangzhou Sunrise...",
    "carrier_hint": "MSC"
  }'
```

Response:
```json
{
  "bol_number": "MEDU4712839",
  "shipper": {
    "name": "Guangzhou Sunrise Electronics Co., Ltd",
    "address": "No. 188 Huangpu East Road, Guangzhou, Guangdong 510700, China"
  },
  "consignee": {
    "name": "Pacific Coast Distributors Inc.",
    "address": "2847 Harbor Blvd, Suite 400, Long Beach, CA 90802, USA"
  },
  "carrier": "Mediterranean Shipping Company (MSC)",
  "vessel_name": "MSC ISABELLA",
  "port_of_loading": "Nansha, China",
  "port_of_discharge": "Long Beach, USA",
  "containers": [
    {"number": "MSCU7834521", "size": "40HC", "seal_number": "CN2847391", "weight_kg": 18450.0},
    {"number": "MSCU9912847", "size": "40HC", "seal_number": "CN2847392", "weight_kg": 21200.0}
  ],
  "gross_weight_kg": 39650.0,
  "hs_codes": ["8528.52", "8528.59"],
  "freight_terms": "PREPAID",
  "confidence": 0.95
}
```

## Deployment

### Railway

```bash
railway login && railway init && railway up
railway variables set ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Fly.io

```bash
fly launch
fly secrets set ANTHROPIC_API_KEY=sk-ant-xxxxx
fly deploy
```

### Docker

```bash
docker build -t freightparse-api .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-xxxxx freightparse-api
```

## RapidAPI Setup

1. Deploy to Railway or Fly.io (get public URL)
2. Go to https://rapidapi.com/provider
3. Create new API, import `rapidapi_spec.yaml`
4. Set base URL to your deployed app
5. Configure `RAPIDAPI_PROXY_SECRET` in your deployment environment
6. Set pricing tiers and publish

## Pricing Strategy

| Tier | Requests/mo | Price | Target Customer |
|------|-------------|-------|-----------------|
| Free | 50 | $0 | Evaluation |
| Basic | 2,000 | $29/mo | Small forwarder |
| Pro | 20,000 | $149/mo | Mid-size logistics |
| Enterprise | 100,000 | $499/mo | Platform integration |

## Cost Analysis

- Claude API cost: ~$0.02 per document
- At $0.15/doc with 87% margin: profitable from day one
- Manual processing cost: $3.33/doc — you save customers 95%
- Break even on hosting: ~200 calls/month

## Auth

Two auth modes:
- **RapidAPI**: Set `RAPIDAPI_PROXY_SECRET` env var. RapidAPI sends it in `X-RapidAPI-Proxy-Secret` header.
- **Direct**: Set `API_KEYS` env var (comma-separated). Callers send key in `X-API-Key` header.

## License

MIT
