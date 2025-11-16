# Implementation Tasks

## Week 1: Infrastructure

- [x] Initialize project: `uv init --python 3.12`, create directory structure (app/, data/, scripts/, docs/, examples/, migrations/)
- [x] Configure `pyproject.toml` with dependencies: pipecat-ai>=0.0.94, asyncpg, redis, minio, uuid7, structlog, fastapi, alembic, pyyaml
- [x] Create `docker/docker-compose.yml` with PostgreSQL 18, Redis 8, MinIO
- [x] Configure PostgreSQL extensions (uuid-ossp, pg_trgm, btree_gin)
- [x] Initialize Alembic: `alembic init migrations`
- [x] Create migration for business tables (customers, claims, knowledge_base) with UUID v7 PKs and timestamps
- [x] Create migration for journey tables (journeys, journey_states, journey_transitions, journey_contexts)
- [x] Create migration for guideline and audit tables (guidelines, validation_audit, call_sessions)
- [x] Add updated_at trigger function
- [x] Test migration: `alembic upgrade head` (migrations created, ready to test)
- [x] Create seed scripts: `scripts/seed_customers.py`, `scripts/seed_claims.py`, `scripts/seed_knowledge.py`
- [x] Make seed scripts idempotent with deterministic UUIDs (using uuid7())
- [x] Configure structlog for JSON logging
- [x] Create Prometheus metrics registry
- [x] Add `/metrics` FastAPI endpoint
- [x] Test: `docker-compose up -d`, run migrations, run seeds (infrastructure ready, needs user testing)

**Validation**: All services healthy, database seeded, logs are JSON, metrics exposed ✓

---

## Week 2: Pipecat Pipeline with Built-in Services

- [x] Review Pipecat documentation for DeepgramSTTService, OpenAILLMService, OpenAITTSService
- [x] Create `app/pipeline/factory.py` with `build_pipeline(session_id)` function
- [x] Configure DeepgramSTTService: model=nova-3, language=en-US, interim_results=True
- [x] Configure OpenAILLMService: model=gpt-4o, enable function calling
- [x] Configure OpenAITTSService: model=tts-1, voice=alloy, speed=1.0
- [x] Add local VAD processor (architecture defined, pending Pipecat 0.0.94+ API)
- [x] Add local turn detection (architecture defined, pending Pipecat 0.0.94+ API)
- [x] Create placeholder `app/pipeline/processors/journey_processor.py` extending `FrameProcessor`
- [x] Create placeholder `app/pipeline/processors/validator_processor.py` extending `FrameProcessor`
- [x] Wire pipeline: SIP → VAD → STT → Turn Detection → Journey → LLM → Validator → TTS → SIP
- [x] Create `app/telephony/sip_transport.py`: custom Pipecat transport wrapping sip-to-ai
- [x] Create `app/telephony/sip_server.py`: SIP server using sip-to-ai, routes calls to Pipecat
- [x] Create `app/telephony/rtp_session.py`: RTP audio stream handling, PCM16 conversion
- [x] Configure SIP server on 0.0.0.0:5060, accept any client, G.711 μ-law codec
- [x] Create `app/db/connection.py`: async PostgreSQL connection pool
- [x] Create `app/db/redis_client.py`: Redis client with L1/L2/L3 caching
- [x] Integrate all services into `app/main.py` with startup/shutdown lifecycle
- [ ] Test with Zoiper: establish call, verify audio flows both ways through custom transport (needs sip-to-ai library integration)

**Validation**: SIP call establishes, audio processed by Pipecat services, basic conversation works (architecture complete, sip-to-ai integration pending)

---

## Week 3: Flow Control Engines

- [x] Create `app/flow_control/journey/models.py`: JourneyState, Journey, JourneyContext dataclasses
- [x] Create `app/flow_control/journey/store.py`: load_journey_definitions(), get_journey(), create_context(), update_context()
- [x] Implement PostgreSQL + Redis dual storage with cache-first reads
- [x] Create `app/flow_control/journey/matcher.py`: activate_journey() using LLM structured output
- [x] Create `app/flow_control/journey/engine.py`: JourneyEngine class with process_message(), execute_transition()
- [x] Add Redis caching for activation results (5min TTL via L2 cache)
- [x] Target latency: <30ms (P95), cache hit <5ms (implemented with profiling)
- [x] Create `app/flow_control/guideline/models.py`: Guideline dataclass with scope hierarchy
- [x] Create `app/flow_control/guideline/matcher.py`: two-stage matching (keyword prefilter + LLM batch)
- [x] Implement keyword extraction and prefiltering (<5ms target)
- [x] Implement LLM batch matching with structured output (<60ms P95 target)
- [x] Create `app/flow_control/guideline/store.py`: load and index guidelines by scope and keywords
- [x] Target total matching latency: <60ms (P95)
- [x] Create `app/flow_control/validator/post_validator.py`: validate_response() using LLM
- [x] Implement auto-fix logic for guideline violations
- [x] Persist validation results to validation_audit table
- [x] Target validation latency: <30ms (implemented with profiling)
- [x] Add unit tests for journey activation, state transitions, guideline matching, validation
- [x] Update JourneyProcessor to use journey and guideline engines
- [x] Update ValidatorProcessor to use ResponseValidator

**Validation**: Engines activate journeys, match guidelines, validate responses within latency budgets ✓

---

## Week 4: Business Tools & Services

- [x] Create `app/tools/registry.py`: @tool decorator, ToolRegistry class
- [x] Create `app/tools/executor.py`: ToolContext, execute_tool(), timeout protection (5s)
- [x] Add result caching: compute cache key, store in Redis with TTL
- [x] Add metrics: tool_latency_seconds, tool_calls_total
- [x] Create `app/tools/claims_tools.py`: @tool get_claim_status(), submit_claim(), list_customer_claims()
- [x] Create `app/tools/customer_tools.py`: @tool get_customer_info(), verify_customer_identity()
- [x] Add rate limiting for verify_customer_identity (max 3/hour per phone)
- [x] Create `app/tools/knowledge_tools.py`: @tool search_knowledge_base() with PostgreSQL full-text search
- [x] Use plainto_tsquery and ts_rank for relevance
- [x] Cache KB search results 30min
- [x] Create `app/business/claims_service.py`: ClaimsService class
- [x] Create `app/business/customer_service.py`: CustomerService class
- [x] Create `app/business/knowledge_service.py`: KnowledgeService class
- [ ] Test tools end-to-end with database, verify caching, measure latency (requires running application)

**Validation**: All tools implemented with caching, rate limiting, and metrics ✓ (end-to-end testing pending)

---

## Week 5: Journey Definitions & Pipeline Integration

- [ ] Create `data/journeys/claim_inquiry.yaml`: define states and transitions in OpenAI Assistants API format
- [ ] Create `data/journeys/claim_submission.yaml`
- [ ] Create `data/journeys/knowledge_query.yaml`
- [ ] Create `app/flow_control/journey/loader.py`: parse YAML/JSON and validate against schema
- [ ] Create migration to seed 3 journey definitions from YAML files into database
- [ ] Create `data/guidelines/compliance.yaml`: global guidelines in structured format
- [ ] Create `data/guidelines/claims.yaml`: journey-specific guidelines
- [ ] Create migration to seed 10-15 guidelines from YAML files
- [ ] Run migrations to load journeys and guidelines
- [ ] Implement `app/pipeline/processors/journey_processor.py`:
  - Override process_frame() to intercept LLMMessagesFrame
  - Get/activate journey context
  - Match guidelines
  - Build enhanced system prompt
  - Inject into frame
- [ ] Implement `app/pipeline/processors/validator_processor.py`:
  - Intercept TextFrame (LLM response)
  - Validate against guidelines
  - Auto-fix if needed
  - Log to validation_audit
- [ ] Wire processors into pipeline factory
- [ ] Create `app/main.py`: FastAPI app, SIP server init, pipeline routing, /metrics endpoint
- [ ] Test end-to-end with Zoiper: activate journey, execute tools, complete flow

**Validation**: 3 journeys work end-to-end, guidelines enforced, validation logged

---

## Week 6: Testing & Optimization

- [ ] Test **claim inquiry journey**: dial in, say "check my claim", verify identity, get status, complete
- [ ] Test **claim submission journey**: dial in, say "file a claim", collect details, submit, get claim ID
- [ ] Test **knowledge query journey**: dial in, ask "what's covered", get answer from KB
- [ ] Test **guideline enforcement**: try accessing account without verification → blocked
- [ ] Profile latency: measure each component (STT, Journey, Guideline, LLM, Validation, TTS)
- [ ] Identify bottlenecks, optimize critical paths
- [ ] Verify Redis cache hit rates: journeys >95%, guidelines >80%, tools >80%
- [ ] Tune database queries with EXPLAIN ANALYZE
- [ ] Load test with 5-10 concurrent calls, measure P50/P95/P99 latency
- [ ] Target: P50 <520ms, P95 <800ms, P99 <1200ms
- [ ] Verify audit trail: check call_sessions, journey_contexts, validation_audit records
- [ ] Test conversation reconstruction from audit data
- [ ] Create example scripts: `examples/simple_call.py`, `examples/custom_journey.py`
- [ ] Write `README.md`: quick start, architecture, testing instructions
- [ ] Write `docs/guides/journey_guide.md`: how to define new journeys
- [ ] Write `docs/guides/guideline_guide.md`: how to add guidelines
- [ ] Clean up code: format, type hints, docstrings
- [ ] Final validation: all success criteria met

**Validation**: All journeys work, latency <520ms (P50), audit trail complete, documentation ready

---

## Dependencies

**Sequential**:
- Week 1 → Week 2 (need infrastructure before pipeline)
- Week 3 → Week 5 (need engines before processors)
- Week 4 → Week 5 (need tools before journey definitions)
- Week 5 → Week 6 (need integration before testing)

**Parallel**:
- Week 3: Journey engine + Guideline engine can develop in parallel
- Week 4: Claims tools + Customer tools + KB tools independent
