# FreightParse API

**Turn messy shipping documents into clean, structured JSON.**

Parses Bills of Lading, freight invoices, and packing lists. Built for freight forwarders, logistics platforms, and supply chain software.

## Endpoints

| Endpoint | Input | Output | Price |
|----------|-------|--------|-------|
| `POST /parse-bol` | Bill of Lading text | Shipper, consignee, containers, ports, weights, HS codes | $0.15/doc |
| `POST /parse-freight-invoice` | Freight invoice text | Charges breakdown, line items, references, totals | $0.15/doc |
| `POST /parse-packing-list` | Packing list text | Items, quantities, weights, dimensions, HS codes | $0.10/doc |
| `POST /parse-batch` | Up to 10 documents | Mixed results with per-doc status | Per-doc pricing |

## Quick Start

### Local Development

```bash
cd freightparse-api
pip install -r requirements.txt

# Set API key
set ANTHROPIC_API_KEY=sk-ant-xxxxx   # Windows
export ANTHROPIC_API_KEY=sk-ant-xxxxx # Linux/Mac

# Set at least one direct API key (no default in v2)
set API_KEYS=my-secret-key
export API_KEYS=my-secret-key

# Run
python main.py
```

Open http://localhost:8000/docs for interactive API docs.

### Test

```bash
pip install pytest pytest-asyncio anyio
pytest tests/ -v
```

## Example: Parse a Bill of Lading

```bash
curl -X POST http://localhost:8000/parse-bol \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-secret-key" \
  -d '{
    "text": "BILL OF LADING\nB/L No: MEDU4712839\nSHIPPER: Guangzhou Sunrise...",
    "carrier_hint": "MSC"
  }'
```

Response includes `X-Request-ID` and `X-Response-Time` headers for tracing.

## Example: Batch Parse

```bash
curl -X POST http://localhost:8000/parse-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-secret-key" \
  -d '{
    "documents": [
      {"doc_type": "bol", "text": "BILL OF LADING...", "carrier_hint": "MSC"},
      {"doc_type": "freight_invoice", "text": "FREIGHT INVOICE..."},
      {"doc_type": "packing_list", "text": "PACKING LIST..."}
    ]
  }'
```

## Deployment

### Railway

```bash
railway login && railway init && railway up
railway variables set ANTHROPIC_API_KEY=sk-ant-xxxxx
railway variables set API_KEYS=your-production-key
```

### Fly.io

```bash
fly launch
fly secrets set ANTHROPIC_API_KEY=sk-ant-xxxxx
fly secrets set API_KEYS=your-production-key
fly deploy
```

### Docker

```bash
docker build -t freightparse-api .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-xxxxx \
  -e API_KEYS=your-production-key \
  freightparse-api
```

## RapidAPI Setup

1. Deploy to Railway or Fly.io (get public URL)
2. Go to https://rapidapi.com/provider
3. Create new API, import `rapidapi_spec.yaml`
4. Set base URL to your deployed app
5. Configure `RAPIDAPI_PROXY_SECRET` in your deployment environment
6. Set pricing tiers and publish

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `API_KEYS` | (empty) | Comma-separated direct API keys |
| `RAPIDAPI_PROXY_SECRET` | (empty) | RapidAPI proxy secret |
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250514` | Claude model to use |
| `CLAUDE_MAX_TOKENS` | `4096` | Max tokens per response |
| `CLAUDE_TIMEOUT` | `60` | API timeout in seconds |
| `RATE_LIMIT_REQUESTS` | `60` | Requests per window |
| `RATE_LIMIT_WINDOW` | `60` | Window in seconds |
| `ALLOWED_ORIGINS` | (all) | CORS origins (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Pricing Strategy

| Tier | Requests/mo | Price | Target Customer |
|------|-------------|-------|-----------------|
| Free | 50 | $0 | Evaluation |
| Basic | 2,000 | $29/mo | Small forwarder |
| Pro | 20,000 | $149/mo | Mid-size logistics |
| Enterprise | 100,000 | $499/mo | Platform integration |

## v2.0 Changes

- **Async Claude client** — no longer blocks the event loop under load
- **Automatic retries** — transient Claude API errors retry 3x automatically
- **Batch endpoint** — parse up to 10 documents in one call
- **Request tracing** — every response includes `X-Request-ID` and `X-Response-Time`
- **Structured logging** — timestamps, levels, and request IDs
- **Prompt injection guard** — detects and warns on suspicious input patterns
- **Security hardening** — no default API keys, configurable CORS, no internal error leaking
- **Improved health check** — verifies Claude API connectivity, not just server status
- **Rate limiter cleanup** — no more memory leak from abandoned rate limit entries
- **Better JSON extraction** — brace-matching parser handles edge cases
- **Carrier hints on all endpoints** — invoice and packing list now accept hints too
- **pytest test suite** — 15+ automated tests with mocked Claude responses

## Auth

Two auth modes:
- **RapidAPI**: Set `RAPIDAPI_PROXY_SECRET` env var. RapidAPI sends it in `X-RapidAPI-Proxy-Secret` header.
- **Direct**: Set `API_KEYS` env var (comma-separated). Callers send key in `X-API-Key` header.

## License

MIT
