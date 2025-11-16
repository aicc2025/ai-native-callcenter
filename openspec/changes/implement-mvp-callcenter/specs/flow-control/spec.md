# Capability: Flow Control

## ADDED Requirements

### Requirement: Journey Engine
The system SHALL implement a Journey engine that manages conversation state machines stored in PostgreSQL with Redis caching.

#### Scenario: Journey definition loading
**Given** application starts
**When** journey definitions load
**Then** journeys SHALL be parsed from YAML/JSON files following OpenAI Assistants API format
**And** parsed journeys SHALL be validated against schema
**And** all journeys SHALL be loaded from PostgreSQL into Redis cache
**And** cache SHALL be indefinite with manual invalidation
**And** each journey SHALL include: id, name, activation_conditions, states, transitions, initial_state

#### Scenario: Journey activation
**Given** user message with no active journey
**When** activation is attempted
**Then** LLM structured output SHALL evaluate activation conditions
**And** if confidence >0.7, journey SHALL activate
**And** journey context SHALL be created in database and Redis: session_id, journey_id, current_state, variables, activated_at
**And** activation SHALL complete in <30ms (P95), cache hit <5ms

#### Scenario: State transitions
**Given** active journey with current state
**When** user provides input
**Then** transition conditions SHALL be evaluated via LLM
**And** highest priority satisfied transition SHALL be selected
**And** current_state SHALL update to target_state
**And** state history SHALL be appended
**And** context SHALL persist to database and Redis

#### Scenario: State guidance injection
**Given** active journey state
**When** LLM prompt is built
**Then** state action field SHALL be injected into system prompt
**And** if tool state, tools SHALL be called before LLM

---

### Requirement: Guideline Engine
The system SHALL implement a Guideline engine with two-stage matching: keyword pre-filter followed by LLM batch matching.

#### Scenario: Guideline loading
**Given** application starts
**When** guidelines load
**Then** all enabled guidelines SHALL load from PostgreSQL into Redis
**And** guidelines SHALL be indexed by scope (GLOBAL, JOURNEY, STATE) and keywords
**And** each guideline SHALL include: id, scope, condition, action, tools, priority, keywords

#### Scenario: Two-stage matching
**Given** user message and journey context
**When** guideline matching occurs
**Then** stage 1 (keyword pre-filter) SHALL complete in <5ms
**And** stage 1 SHALL extract message keywords and match against guideline keywords
**And** stage 1 SHALL filter to 10-20 candidates from 100+ total
**And** stage 2 (LLM batch match) SHALL complete in <50ms (P50), <60ms (P95)
**And** stage 2 SHALL use structured output to evaluate conditions
**And** matches with confidence >0.6 SHALL be returned
**And** total matching SHALL complete in <60ms (P95)

#### Scenario: Priority resolution
**Given** multiple guidelines matched
**When** applying to system prompt
**Then** priority resolution SHALL occur in two stages: (1) scope type (state > journey > global), (2) within same scope, numeric priority DESC
**And** state-specific guidelines SHALL have highest priority
**And** journey-specific guidelines SHALL have medium priority
**And** global guidelines SHALL have lowest priority
**And** conflicting actions SHALL resolve by highest priority wins

---

### Requirement: Response Validator
The system SHALL implement response validation using LLM structured output to check guideline compliance.

#### Scenario: Post-validation
**Given** LLM generates response
**When** post-validation runs
**Then** response SHALL be validated against active guidelines via LLM
**And** structured output SHALL return: is_valid, violations, suggested_fixes, confidence
**And** if invalid with confidence >0.8, auto-fix SHALL be attempted
**And** if still invalid after 1 retry, error SHALL be returned
**And** validation SHALL complete in <30ms (P95)

#### Scenario: Validation audit
**Given** any validation check
**When** validation completes
**Then** record SHALL be created in validation_audit table
**And** record SHALL include: session_id, journey_id, is_valid, violations, confidence, latency_ms
**And** audit trail SHALL enable conversation reconstruction

---

### Requirement: Context Management
The system SHALL manage journey runtime context in PostgreSQL (persistence) and Redis (performance).

#### Scenario: Session context creation
**Given** new SIP call established
**When** session initializes
**Then** context SHALL be created: session_id, call_id, customer_id, started_at, variables
**And** context SHALL write to PostgreSQL and Redis
**And** Redis TTL SHALL be call duration + 1 hour

#### Scenario: Context retrieval
**Given** request for session context
**When** retrieval executes
**Then** Redis SHALL be tried first (<2ms)
**And** if cache miss, PostgreSQL SHALL be queried (<10ms)
**And** result SHALL populate Redis for future hits
**And** 95%+ requests SHALL be cache hits after warm-up

---

### Requirement: Graceful Degradation
The system SHALL degrade gracefully when flow control components fail.

#### Scenario: Journey engine failure
**Given** journey engine fails
**When** failure is detected
**Then** conversation SHALL continue WITHOUT journey control
**And** LLM SHALL operate in freeform mode
**And** flag `journey_bypassed=true` SHALL be set
**And** error SHALL be logged
**And** call SHALL NOT drop

#### Scenario: Guideline timeout
**Given** guideline matching exceeds 100ms
**When** timeout detected
**Then** empty guideline list SHALL be returned
**And** timeout warning SHALL be logged
**And** conversation SHALL continue
**And** circuit breaker SHALL open for 60s after repeated timeouts

#### Scenario: Validation bypass
**Given** validation fails or times out
**When** failure detected
**Then** LLM response SHALL proceed without validation
**And** flag `validation_bypassed=true` SHALL be set
**And** critical guidelines (PII) SHALL still be checked via regex
**And** bypass SHALL be flagged for manual review
