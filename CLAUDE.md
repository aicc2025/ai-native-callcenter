# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Development Commands

### Setup and Infrastructure
```bash
# Setup environment
cp .env.example .env  # Edit with your OpenAI and Deepgram API keys

# Install dependencies
pip install -e ".[dev]"

# Start infrastructure (PostgreSQL 18, Redis 8, MinIO)
cd docker && docker-compose up -d

# Run database migrations
alembic upgrade head

# Seed mock data (customers, claims, knowledge base)
python scripts/seed_customers.py
python scripts/seed_claims.py
python scripts/seed_knowledge.py
```

### Running the Application
```bash
# Start FastAPI server (http://localhost:8000)
python app/main.py

# View metrics
curl http://localhost:8000/metrics
```

### Development Tools
```bash
# Format code (100 char line length)
black app/ scripts/

# Type checking (strict mode enabled)
mypy app/

# Run tests
pytest
pytest tests/test_journey_engine.py  # Single test file
```

### Database Operations
```bash
# Create new migration
alembic revision -m "description"

# Rollback migration
alembic downgrade -1

# View current version
alembic current
```

## Architecture Overview

### Layered Architecture
The system follows strict **single-directional dependencies**: Telephony → Pipeline → Flow Control → Business → Data

```
┌─────────────────────────────────────────────────────────────┐
│ Telephony Layer (app/telephony/)                            │
│ - SIPTransport: Custom Pipecat transport wrapping sip-to-ai│
│ - RTPSession: G.711 μ-law codec handling                    │
│ - SIPServer: Routes calls to Pipecat pipelines             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Pipeline Layer (app/pipeline/)                              │
│ - PipecatPipelineFactory: Creates STT/LLM/TTS services     │
│ - JourneyProcessor: Injects journey context into frames    │
│ - ValidatorProcessor: Validates responses against rules    │
│ Flow: SIP → VAD → STT → Turn → Journey → LLM → Validator → TTS → SIP
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Flow Control Layer (app/flow_control/)                      │
│ - Journey Engine: State machines from YAML definitions     │
│ - Guideline Engine: Two-stage matching (keyword + LLM)     │
│ - Response Validator: ARQ-inspired validation              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Business Layer (app/business/, app/tools/)                  │
│ - ClaimsService, CustomerService, KnowledgeService         │
│ - Function calling tools with 30min cache TTL              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Data Layer (app/db/)                                        │
│ - PostgreSQL: UUID v7 PKs, auto-updated timestamps         │
│ - Redis: L1 (definitions), L2 (activations 5min), L3 (tools 30min)
└─────────────────────────────────────────────────────────────┘
```

### Key Concepts

**Journey**: State machine for conversation flows (e.g., claim_inquiry, claim_submission). Defined in `data/journeys/*.yaml` following OpenAI Assistants API format, loaded into PostgreSQL.

**Guideline**: Business rules constraining AI behavior (e.g., "verify identity before account access"). Two-stage matching:
1. Keyword pre-filter (<5ms) narrows candidates from 100+ to 10-20
2. LLM batch matching (<60ms P95) evaluates conditions with structured output

**Pipecat Integration**: Uses built-in services (DeepgramSTTService with Nova-3, OpenAILLMService with gpt-4o, OpenAITTSService with tts-1). Custom processors intercept frames to inject journey context and validate responses.

### Critical Implementation Details

**UUID v7 Generation**: All primary keys use `uuid7()` library (time-ordered UUIDs), generated in Python before database insert.

**Database Triggers**: All tables have `created_at`/`updated_at` timestamps. The `update_updated_at_column()` trigger auto-updates `updated_at` on row modifications.

**Multi-Level Caching**:
- L1 (hot): Journey/guideline definitions, indefinite TTL
- L2 (warm): Journey activation results, 5min TTL
- L3 (cold): Tool execution results, 30min TTL

**Async-First**: All I/O operations use `async/await`. Database pool (asyncpg) and Redis client are async. Main application lifecycle in FastAPI startup/shutdown events.

**Pipecat Frame Processing**: Custom processors extend `FrameProcessor` and override `process_frame()`. JourneyProcessor intercepts `LLMMessagesFrame` to inject context before LLM, ValidatorProcessor intercepts `TextFrame` to validate responses after LLM.

## Performance Targets

- **End-to-end latency**: <520ms (P50), <800ms (P95), <1200ms (P99)
- **Component breakdown**: STT ~100ms, Journey matching ~30ms, Guideline matching <60ms (P95), LLM ~200ms, Validation ~30ms, TTS ~100ms
- **Database queries**: Simple (single table) <30ms, Complex (joins/FTS) <50ms (P95)
- **Cache hit rates**: Journeys >95%, Guidelines >80%, Tools >80%

## Code Conventions

- **No Claude signatures**: User handles git operations manually
- **English only**: No Chinese comments or strings in code
- **Type hints**: Required for all public APIs (`mypy` strict mode)
- **Async everywhere**: All I/O must use `async/await`
- **Structured logging**: Use `structlog` with JSON output, include `session_id`, `call_id`, `journey_id` in context

## Implementation Status

**Current**: Week 4 complete (67% done). See `openspec/changes/implement-mvp-callcenter/tasks.md` for detailed task tracking.

**Completed**:
- Week 1: Infrastructure (PostgreSQL/Redis/MinIO, migrations, seed scripts)
- Week 2: Pipecat pipeline architecture (factory, processors, SIP transport layer, DB/Redis clients)
- Week 3: Flow control engines (Journey, Guideline, Validator - fully integrated into processors)
- Week 4: Business tools & services (Tool registry/executor, ClaimsService, CustomerService, KnowledgeService with full-text search)

**Pending**: YAML journey definitions + integration (Week 5), testing + optimization (Week 6).
- tasks.md — the official OpenSpec task list and the only authoritative task-tracking document.