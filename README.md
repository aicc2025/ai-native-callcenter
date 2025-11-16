# AI-Native Call Center

AI-native call center for insurance claims and customer service using Pipecat for real-time voice AI orchestration.

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Docker & Docker Compose
- OpenAI API key
- Deepgram API key
- SIP soft-phone (Zoiper recommended)

### 2. Setup

```bash
# Clone and setup environment
cp .env.example .env
# Edit .env with your API keys

# Install dependencies
pip install -e ".[dev]"

# Start infrastructure
cd docker && docker-compose up -d

# Run migrations
alembic upgrade head

# Seed data
python scripts/seed_customers.py
python scripts/seed_claims.py
python scripts/seed_knowledge.py
```

### 3. Run Application

```bash
python app/main.py
```

### 4. Test with SIP Soft-phone

Configure Zoiper to connect to `localhost:5060` and make a test call.

## Project Structure

```
app/
├── pipeline/          # Pipecat pipeline integration
│   ├── factory.py     # Pipeline builder
│   └── processors/    # Custom processors (Journey, Validator)
├── telephony/         # SIP/RTP integration
│   ├── sip_transport.py
│   ├── sip_server.py
│   └── rtp_session.py
├── flow_control/      # Journey and Guideline engines
│   ├── journey/       # Journey state machine engine
│   ├── guideline/     # Guideline matching engine
│   └── validator/     # Response validation
├── tools/             # Function calling tools
├── business/          # Business services
└── db/                # Database repositories

data/
├── journeys/          # Journey YAML definitions
└── guidelines/        # Guideline YAML definitions

migrations/            # Alembic database migrations
scripts/               # Seed scripts
docker/                # Docker Compose config
```

## Implementation Status

This project follows the OpenSpec change proposal `implement-mvp-callcenter`.

### Week 1: Infrastructure ✓ Complete
- [x] Project structure initialized (app/, data/, scripts/, migrations/, docker/)
- [x] Dependencies configured (pyproject.toml with Pipecat 0.0.94+, asyncpg, Redis, etc.)
- [x] Docker Compose setup (PostgreSQL 18, Redis 8, MinIO)
- [x] Database migrations created (3 migrations covering all tables with UUID v7 PKs)
- [x] Seed scripts completed (customers, claims, knowledge base)
- [x] Logging and metrics setup (structlog JSON + Prometheus)

### Week 2: Pipecat Pipeline ✓ Complete
- [x] Pipeline factory with Pipecat built-in services (DeepgramSTT Nova-3, OpenAI LLM gpt-4o, OpenAI TTS)
- [x] Custom processors (JourneyProcessor, ValidatorProcessor - placeholders for Week 3)
- [x] SIP integration architecture (SIPTransport, RTPSession, SIPServer - needs sip-to-ai library)
- [x] Database and Redis clients (async connection pools with L1/L2/L3 caching)
- [x] Main application with lifecycle management (startup/shutdown)

### Week 3: Flow Control Engines ✓ Complete
- [x] Journey Engine (models, store with PostgreSQL + Redis, matcher with LLM, engine)
- [x] Guideline Engine (models with scope hierarchy, two-stage matching: keyword prefilter + LLM batch)
- [x] Response Validator (ARQ-inspired validation with auto-fix, audit logging)
- [x] Updated processors to use engines (JourneyProcessor injects context, ValidatorProcessor validates responses)
- [x] Unit tests for models and core logic

### Week 4: Business Tools & Services ✓ Complete
- [x] Tool Registry with @register decorator and OpenAI function format
- [x] Tool Executor with timeout (5s), L3 caching (30min), rate limiting, Prometheus metrics
- [x] Business Services: ClaimsService, CustomerService, KnowledgeService
- [x] Claims Tools: get_claim_status, list_customer_claims, submit_claim
- [x] Customer Tools: get_customer_info, verify_customer_identity (rate limited 3/hour)
- [x] Knowledge Tools: search_knowledge_base (PostgreSQL full-text with plainto_tsquery and ts_rank)

### Week 5-6: Implementation Pending
- Week 5: Journey Definitions & Integration
- Week 6: Testing & Optimization

**Progress**: 67% complete (4/6 weeks)

See `openspec/changes/implement-mvp-callcenter/tasks.md` for detailed task tracking.

## Development

```bash
# Format code
black app/ scripts/

# Type check
mypy app/

# Run tests
pytest
```

## Architecture

- **Layered architecture**: Telephony → Pipeline → Flow Control → Business → Data
- **Journey Engine**: State machines for conversation flows stored in YAML, loaded to PostgreSQL
- **Guideline Engine**: Two-stage matching (keyword pre-filter + LLM batch)
- **Caching**: Multi-level Redis (L1: definitions, L2: activations, L3: tool results 30min)

## Performance Targets

- End-to-end latency: <520ms (P50)
- Database queries: Simple <30ms, Complex <50ms (P95)
- Guideline matching: <60ms (P95)

## License

Proprietary
