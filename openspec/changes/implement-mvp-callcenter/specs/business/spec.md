# Capability: Business

## ADDED Requirements

### Requirement: Claims Tools
The system SHALL provide function calling tools for claims management operations.

#### Scenario: Get claim status
**Given** claim ID
**When** tool `get_claim_status(claim_id)` is called
**Then** claim SHALL be queried from PostgreSQL
**And** result SHALL be cached in Redis for 30 minutes
**And** execution SHALL complete in <50ms (P95)
**And** result SHALL include: status, amount, description, submitted_at, last_updated
**And** if not found, `found=false` SHALL be returned without error

#### Scenario: Submit new claim
**Given** customer ID and claim details
**When** tool `submit_claim(customer_id, claim_type, amount, description)` is called
**Then** parameters SHALL be validated: customer_id is UUID, claim_type in [auto,health,property], amount >0
**And** new claim SHALL be created with UUID v7 id, status "submitted"
**And** history SHALL record: status=submitted, at=now, by=ai
**And** claim_id SHALL be returned
**And** execution SHALL complete in <100ms (P95)

#### Scenario: List customer claims
**Given** customer ID
**When** tool `list_customer_claims(customer_id, limit=10)` is called
**Then** claims SHALL be queried ordered by created_at DESC
**And** results SHALL be cached for 30 minutes
**And** limit SHALL default to 10, max 50
**And** claim summaries SHALL be returned

---

### Requirement: Customer Tools
The system SHALL provide function calling tools for customer management operations.

#### Scenario: Get customer info
**Given** customer ID or phone
**When** tool `get_customer_info(customer_id, phone)` is called
**Then** at least one parameter SHALL be required
**And** customer SHALL be queried from PostgreSQL
**And** result SHALL be cached for 30 minutes
**And** execution SHALL complete in <30ms (P95)
**And** customer record SHALL be returned: id, name, phone, email, policy_number

#### Scenario: Verify identity
**Given** phone and policy number
**When** tool `verify_customer_identity(phone, policy_number)` is called
**Then** customer SHALL be queried by phone
**And** policy_number SHALL be checked for match
**And** result SHALL return: verified (bool), customer_id, confidence
**And** if verified, customer_id SHALL be stored in session context
**And** verification attempt SHALL be logged to audit
**And** rate limiting SHALL prevent brute force: max 3 attempts per phone per hour

---

### Requirement: Knowledge Base Tools
The system SHALL provide function calling tools for knowledge base search using PostgreSQL full-text search.

#### Scenario: Search knowledge base
**Given** category and query
**When** tool `search_knowledge_base(category, query)` is called
**Then** Redis cache SHALL be checked: `kb:{category}:{query_hash}`
**And** if cache miss, PostgreSQL full-text search SHALL execute
**And** `plainto_tsquery` SHALL parse query
**And** search_vector SHALL be queried with `ts_rank` ordering
**And** top 3 results SHALL be returned
**And** results SHALL be cached for 30 minutes
**And** execution SHALL complete in <50ms (P95)
**And** cache hit rate SHALL be >80% after warm-up

---

### Requirement: Tool Execution Framework
The system SHALL provide a framework for tool registration, execution, caching, and monitoring.

#### Scenario: Tool registration
**Given** application starts
**When** tools are registered
**Then** each tool SHALL be decorated with: name, description, parameter schema
**And** tools SHALL be discoverable via ToolRegistry
**And** tool definitions SHALL serialize to OpenAI function calling format

#### Scenario: Tool execution with context
**Given** LLM function call request
**When** tool executor runs
**Then** parameters SHALL be validated against schema
**And** ToolContext SHALL be created with: session_id, journey_id, db, redis, minio
**And** tool function SHALL execute asynchronously
**And** latency SHALL be measured
**And** metrics SHALL be recorded: tool_latency_seconds{tool_name}, tool_calls_total{tool_name,status}
**And** ToolResult or ToolError SHALL be returned

#### Scenario: Result caching
**Given** read-only tool execution completes
**When** result is cacheable
**Then** cache key SHALL be computed: `tool:{tool_name}:{params_hash}`
**And** result SHALL serialize to JSON
**And** result SHALL store in Redis with TTL: read ops 30min, search 30min, write no cache
**And** subsequent identical calls SHALL return cached result

#### Scenario: Error handling
**Given** tool execution fails
**When** error occurs
**Then** if transient (connection timeout, deadlock), retry up to 2 times
**And** if permanent (constraint violation), do NOT retry
**And** structured error SHALL return: error message, code, retryable flag
**And** error SHALL be logged with stack trace
**And** timeout protection SHALL cancel execution after 5 seconds

---

### Requirement: Business Services
The system SHALL implement service layer for business logic separate from tool layer.

#### Scenario: Service layer responsibilities
**Given** tool calls business service
**When** service executes
**Then** service SHALL handle: validation, transformations, business rules
**And** service SHALL be async
**And** service SHALL use database repositories for data access
**And** services SHALL exist: ClaimsService, CustomerService, KnowledgeService
