# Project Context

## Purpose

Build an AI-native call center system for insurance claims and customer service using Pipecat for real-time voice AI orchestration with custom Journey and Guideline engines for business flow control.

## Tech Stack

- **Language**: Python 3.12+
- **AI Framework**: Pipecat 0.0.94+ (STT, LLM, TTS services)
- **Database**: PostgreSQL 18 with UUID v7 primary keys
- **Cache**: Redis 8
- **Storage**: MinIO
- **Web**: FastAPI + Uvicorn
- **Monitoring**: structlog + basic Prometheus metrics
- **Deployment**: Docker Compose (MVP)

## Project Conventions

### Code Style
- All code in English (no Chinese comments or strings)
- Use `async/await` for all I/O operations
- Type hints required for public APIs
- Format with `black` or `ruff`
- Docstrings for classes and public methods

### Architecture Patterns
- **Layered architecture**: Telephony → Pipeline → Flow Control → Business → Data
- **Single-directional dependencies**: Upper layers depend on lower layers only
- **UUID v7**: Python-generated (using `uuid7` library) for all primary keys
- **Timestamps**: All tables have `created_at` and `updated_at` (auto-updated via trigger)
- **Caching**: Multi-level Redis caching (L1: definitions, L2: activations, L3: tool results 30min)
- **Journey definitions**: YAML/JSON files following OpenAI Assistants API format, loaded into PostgreSQL
- **SIP integration**: Custom Pipecat transport layer in `app/telephony/` wrapping sip-to-ai RTP streams
- **Data privacy**: MVP uses mock data only - no real customer PII, no compliance requirements

### Testing Strategy
- Unit tests for flow control engines and tools
- Integration tests for Pipecat pipeline
- Manual E2E testing with SIP soft-phone (Zoiper)
- Performance testing: target <520ms P50 latency

### Git Workflow
- No Claude signatures in code
- User handles `git push` manually
- Conventional commits preferred

## Domain Context

**Insurance Call Center**: Handle incoming calls for:
- Claim inquiries (check status, timeline)
- Claim submissions (file new claims)
- Knowledge base queries (policy questions, FAQs)

**Journey**: A state machine representing a business conversation flow (e.g., "claim_inquiry")
**Guideline**: Business rules that constrain AI behavior (e.g., "verify identity before account access")
**Tool**: Function calling integration for database/service operations

## Important Constraints

- **MVP scope**: 4-6 weeks, 3 core journeys only
- **No authentication**: MVP has no API auth
- **Simplified monitoring**: No LGTM Stack (just logs + basic metrics)
- **SIP soft-phone only**: No real telephony provider integration
- **Simulated data**: Mock customers, claims, knowledge base
- **Latency budget**: <520ms end-to-end (P50)

## External Dependencies

- **OpenAI API**: gpt-4o (LLM), tts-1 (TTS) - via Pipecat services
- **Deepgram API**: Nova-3 (STT) - via Pipecat service
- **sip-to-ai**: Python SIP/RTP library for telephony integration
