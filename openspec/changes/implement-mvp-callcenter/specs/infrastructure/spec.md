# Capability: Infrastructure

## ADDED Requirements

### Requirement: PostgreSQL Database
The system SHALL provide PostgreSQL 16+ database with UUID v7 primary keys and automatic timestamps for all business data and journey definitions.

#### Scenario: Database initialization with extensions
**Given** a fresh PostgreSQL installation
**When** initialization runs
**Then** extensions SHALL be enabled: uuid-ossp, pg_trgm, btree_gin
**And** database `callcenter` SHALL exist
**And** connection pool SHALL be configured for async operations

#### Scenario: UUID v7 primary keys
**Given** any database table
**When** a record is inserted
**Then** the primary key SHALL be UUID v7 generated in Python using `uuid7` library
**And** all tables SHALL have `created_at` and `updated_at` timestamp columns
**And** `updated_at` SHALL auto-update via database trigger

#### Scenario: Query performance targets
**Given** database queries are executed
**When** performance is measured
**Then** simple queries (single table lookup) SHALL complete in <30ms (P95)
**And** complex queries (joins, full-text search) SHALL complete in <50ms (P95)

---

### Requirement: Redis Cache
The system SHALL provide Redis 7 for multi-level caching of journey definitions, activation results, and tool outputs.

#### Scenario: Cache configuration
**Given** Redis is initialized
**When** configuration is applied
**Then** maxmemory-policy SHALL be `allkeys-lru`
**And** timeout SHALL be 300 seconds
**And** persistence SHALL be disabled for MVP

#### Scenario: Multi-level cache strategy
**Given** cacheable data
**When** caching occurs
**Then** L1 (hot) SHALL cache journey/guideline definitions indefinitely
**And** L2 (warm) SHALL cache activation results for 5 minutes
**And** L3 (cold) SHALL cache tool results for 30 minutes

---

### Requirement: MinIO Object Storage
The system SHALL provide MinIO for storing call recordings and claim documents.

#### Scenario: Bucket initialization
**Given** MinIO starts
**When** buckets are created
**Then** buckets SHALL exist: call-recordings, claim-documents, knowledge-assets
**And** public read policy SHALL be set for MVP
**And** retention SHALL be 30 days

---

### Requirement: Docker Compose Deployment
The system SHALL deploy all services via Docker Compose for local development.

#### Scenario: Single command startup
**Given** Docker is installed
**When** running `docker-compose up -d`
**Then** PostgreSQL, Redis, MinIO SHALL start
**And** all services SHALL be ready within 60 seconds
**And** health checks SHALL pass

#### Scenario: Environment variables
**Given** a `.env` file
**When** Docker Compose reads it
**Then** variables SHALL be supported: POSTGRES_*, REDIS_*, MINIO_*, OPENAI_API_KEY, DEEPGRAM_API_KEY
**And** secrets SHALL NOT be committed to git
**And** `.env.example` template SHALL be provided

---

### Requirement: Database Schema
The system SHALL define tables for customers, claims, knowledge base, journeys, guidelines, and audit trails.

#### Scenario: Core business tables
**Given** migrations run
**When** schema is applied
**Then** tables SHALL exist: customers, claims, knowledge_base
**And** customers SHALL have: id, name, phone, email, policy_number, metadata, timestamps
**And** claims SHALL have: id, customer_id, type, status, amount, description, documents, history, timestamps
**And** knowledge_base SHALL have: id, category, keywords, question, answer, search_vector, timestamps

#### Scenario: Journey tables
**Given** migrations run
**When** schema is applied
**Then** tables SHALL exist: journeys, journey_states, journey_transitions, journey_contexts
**And** journey_contexts SHALL track: session_id, journey_id, current_state, variables, activated_at

#### Scenario: Guideline and audit tables
**Given** migrations run
**When** schema is applied
**Then** tables SHALL exist: guidelines, validation_audit
**And** validation_audit SHALL log all validation checks with violations and confidence

---

### Requirement: Seed Data
The system SHALL provide scripts to populate database with realistic test data.

#### Scenario: Mock data generation
**Given** empty tables
**When** seed scripts run
**Then** 20-30 customers SHALL be created with deterministic UUIDs
**And** 30-50 claims SHALL be created across types and statuses
**And** 50-100 knowledge articles SHALL be created across 4 categories
**And** 3 journey definitions SHALL be loaded
**And** 10-15 guidelines SHALL be loaded
**And** scripts SHALL be idempotent (safe to rerun)

---

### Requirement: Logging and Metrics
The system SHALL provide structured JSON logging and basic Prometheus metrics.

#### Scenario: Structured logging
**Given** any service component
**When** logging occurs
**Then** logs SHALL be JSON format with: timestamp, level, message, call_id, journey_id, context
**And** structlog SHALL be used for logging

#### Scenario: Prometheus metrics
**Given** application is running
**When** `/metrics` endpoint is queried
**Then** metrics SHALL be exposed: journey_activations_total, guideline_matches_total, tool_latency_seconds, response_latency_e2e_seconds, active_calls
**And** metrics SHALL update in real-time
