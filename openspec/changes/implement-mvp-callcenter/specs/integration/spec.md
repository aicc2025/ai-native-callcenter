# Capability: Integration

## ADDED Requirements

### Requirement: End-to-End Call Flow
The system SHALL handle complete call flows from SIP connection to termination through all pipeline stages.

#### Scenario: Successful call with journey
**Given** SIP soft-phone dials in
**When** call is established
**Then** sequence SHALL occur: SIP INVITE → RTP negotiated → welcome message → user speaks → STT transcribes → journey activates → tools called → LLM responds → TTS plays → call terminates
**And** entire flow SHALL complete with <520ms response latency (P50)
**And** all interactions SHALL be logged
**And** journey completion SHALL be recorded

#### Scenario: Multiple journeys in one call
**Given** call completes one journey
**When** user expresses new intent
**Then** new journey SHALL attempt activation
**And** if matched, new journey SHALL start from initial state
**And** multiple journey_contexts SHALL exist for same session
**And** each journey SHALL be independent

#### Scenario: Call interruption handling
**Given** call in progress
**When** caller hangs up (SIP BYE)
**Then** BYE SHALL be detected within 1 second
**And** Pipecat pipeline SHALL terminate
**And** all WebSocket connections SHALL close
**And** call metadata SHALL persist: duration, journeys, guidelines, tools, transcript
**And** Redis session SHALL clean up
**And** resources SHALL release
**And** cleanup SHALL complete within 2 seconds

---

### Requirement: Three Core Journeys
The system SHALL implement three business journeys: claim inquiry, claim submission, and knowledge query.

#### Scenario: Claim inquiry journey
**Given** user wants to check claim status
**When** journey activates
**Then** states SHALL exist: verify_identity, check_claim, provide_status, ask_follow_up, END
**And** verify_identity SHALL use tool `verify_customer_identity`
**And** check_claim SHALL use tools `get_claim_status`, `list_customer_claims`
**And** transitions SHALL guide conversation flow
**And** activation condition SHALL be "user wants to check claim status"

#### Scenario: Claim submission journey
**Given** user wants to submit new claim
**When** journey activates
**Then** states SHALL exist: verify_identity, collect_claim_type, collect_details, confirm_submission, submit_claim, provide_claim_id, END
**And** submit_claim SHALL use tool `submit_claim`
**And** claim_id SHALL be provided to user
**And** activation condition SHALL be "user wants to file new claim"

#### Scenario: Knowledge query journey
**Given** user asks general question
**When** journey activates
**Then** states SHALL exist: identify_category, search_knowledge, provide_answer, ask_follow_up, END
**And** search_knowledge SHALL use tool `search_knowledge_base`
**And** if no answer found, transfer option SHALL be offered
**And** activation condition SHALL be "user asks about policies, coverage, or procedures"

---

### Requirement: Core Guidelines
The system SHALL implement 10-15 guidelines covering compliance, identity, and safety.

#### Scenario: Global compliance guidelines
**Given** any conversation
**When** guidelines are active
**Then** guideline SHALL exist: "No PII Disclosure" (priority 100) - never reveal SSN, full credit card, passwords
**And** guideline SHALL exist: "Identity Verification Required" (priority 90) - verify before account access
**And** guideline SHALL exist: "Transfer to Human" (priority 80) - offer transfer when requested
**And** guideline SHALL exist: "Professional Tone" (priority 50) - maintain professional empathetic tone
**And** guideline SHALL exist: "Fraud Detection" (priority 95) - flag inconsistent information

#### Scenario: Journey-specific guidelines
**Given** claim_submission journey is active
**When** journey guidelines load
**Then** guideline SHALL exist: "Claim Amount Validation" - require documents for claims >$10K
**And** guideline SHALL exist: "Claim Description Required" - ask for detailed incident description

---

### Requirement: Mock Data
The system SHALL provide seed data scripts for realistic testing.

#### Scenario: Customer seed data
**Given** empty customers table
**When** seed script runs
**Then** 20-30 customers SHALL be created with deterministic UUID v7 ids
**And** customers SHALL have realistic: names, phones, emails, policy numbers
**And** script SHALL be idempotent

#### Scenario: Claims seed data
**Given** empty claims table
**When** seed script runs
**Then** 30-50 claims SHALL be created
**And** distribution SHALL be: 40% auto, 30% health, 30% property
**And** statuses SHALL be: 30% submitted, 40% reviewing, 20% approved, 10% denied
**And** amounts SHALL range $500-$50,000

#### Scenario: Knowledge base seed data
**Given** empty knowledge_base table
**When** seed script runs
**Then** 50-100 articles SHALL be created
**And** categories SHALL be: claims (20-25), policies (15-20), billing (10-15), general (5-10)
**And** each article SHALL have: keywords, search_vector, priority

---

### Requirement: Testing Validation
The system SHALL support manual SIP testing and performance validation.

#### Scenario: Manual SIP testing
**Given** system is running
**When** testing with Zoiper
**Then** test cases SHALL pass: basic call, claim inquiry journey, claim submission journey, knowledge query journey, guideline enforcement
**And** latency SHALL be measured
**And** audit trail SHALL be verified

#### Scenario: Performance validation
**Given** system under test
**When** performance is measured
**Then** end-to-end latency SHALL be <520ms (P50) over 20+ calls
**And** database queries SHALL be <50ms (P95)
**And** Redis cache hit rate SHALL be >80% after 10 calls
**And** tool execution SHALL be <100ms (P95)
**And** no memory leaks SHALL occur after 50 calls
**And** CPU usage SHALL be <70% during 5 concurrent calls

#### Scenario: Audit trail completeness
**Given** completed call
**When** querying database
**Then** records SHALL exist: call_sessions, journey_contexts, validation_audit
**And** tool executions SHALL be in logs
**And** metrics SHALL be in /metrics endpoint
**And** all records SHALL link via session_id
**And** conversation SHALL be reconstructible from audit trail
