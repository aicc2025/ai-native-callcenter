# Proposal: Implement MVP Call Center

## Overview

Build a 4-6 week MVP for an AI-native insurance call center using Pipecat's built-in services (DeepgramSTTService, OpenAILLMService, OpenAITTSService) with custom Journey and Guideline engines for conversation flow control.

## Why

The current system needs replacement with an open-source stack to achieve:
- Lower latency (<520ms end-to-end)
- Cost reduction (75% via open-source)
- Full control over conversation flows (native Journey/Guideline engines)
- Business rule compliance with audit trails

This MVP validates the technical approach with 3 core business journeys using Pipecat's standard services to minimize custom integration work.

## What

### Core Components
1. **Infrastructure**: PostgreSQL, Redis, MinIO (Docker Compose)
2. **Pipecat Pipeline**: Use built-in DeepgramSTTService, OpenAILLMService, OpenAITTSService
3. **Flow Control**: Custom Journey Engine + Guideline Engine (lightweight, database-backed)
4. **Business Tools**: Claims, customer, knowledge base function calling tools
5. **SIP Integration**: sip-to-ai for soft-phone testing (Zoiper)

### In Scope
- 3 journeys: claim inquiry, claim submission, knowledge query
- Journey/Guideline definitions in PostgreSQL (dynamic)
- Mock data: 20-30 customers, 30-50 claims, 50-100 KB articles
- Local VAD and turn detection
- Simplified monitoring (structlog + Prometheus metrics)
- No API authentication

### Out of Scope
- Custom STT/LLM/TTS clients (use Pipecat services)
- Real telephony provider integration
- Full LGTM Stack
- Authentication/authorization
- Production deployment (K8s)

## Success Criteria

- [ ] SIP soft-phone connects and completes calls
- [ ] 3 journeys activate and execute correctly
- [ ] Tool calling works (claims, customer, KB)
- [ ] Latency <520ms (P50)
- [ ] Guidelines enforce business rules
- [ ] Audit trail persisted

## Dependencies

- Pipecat 0.0.94+ with DeepgramSTTService, OpenAILLMService, OpenAITTSService
- OpenAI API (gpt-4o, tts-1)
- Deepgram API (Nova-3)
- sip-to-ai library
- Docker Compose

## Timeline

- Week 1: Infrastructure + database schema
- Week 2: Pipecat pipeline with built-in services
- Week 3: Journey + Guideline engines
- Week 4: Business tools + services
- Week 5: Journey definitions + integration
- Week 6: Testing + optimization

## Risks

| Risk | Mitigation |
|------|------------|
| Pipecat service API changes | Pin exact version |
| Latency exceeds budget | Profile early, optimize critical paths |
| Journey engine performance | Aggressive Redis caching |

## Affected Capabilities

- `infrastructure` - Database, cache, storage
- `pipeline` - Pipecat services integration
- `flow-control` - Journey and Guideline engines
- `business` - Tools and services
- `integration` - End-to-end call flow
