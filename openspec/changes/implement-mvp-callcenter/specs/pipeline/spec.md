# Capability: Pipeline

## ADDED Requirements

### Requirement: Pipecat Services Integration
The system SHALL use Pipecat's built-in DeepgramSTTService, OpenAILLMService, and OpenAITTSService for speech-to-text, language model, and text-to-speech processing.

#### Scenario: DeepgramSTTService configuration
**Given** Pipecat pipeline is initialized
**When** STT service is created
**Then** DeepgramSTTService SHALL be configured with Nova-3 model
**And** language SHALL be en-US
**And** interim results SHALL be enabled
**And** API key SHALL be from environment variable

#### Scenario: OpenAILLMService configuration
**Given** Pipecat pipeline is initialized
**When** LLM service is created
**Then** OpenAILLMService SHALL be configured with gpt-4o model
**And** function calling SHALL be enabled
**And** API key SHALL be from environment variable

#### Scenario: OpenAITTSService configuration
**Given** Pipecat pipeline is initialized
**When** TTS service is created
**Then** OpenAITTSService SHALL be configured with tts-1 model
**And** voice SHALL be `alloy`
**And** speed SHALL be 1.0 (normal)

---

### Requirement: Local VAD and Turn Detection
The system SHALL use local (non-cloud) voice activity detection and turn detection for conversation flow management.

#### Scenario: Local VAD configuration
**Given** Pipecat pipeline includes VAD
**When** VAD processes audio
**Then** VAD SHALL run locally (no external API)
**And** VAD SHALL detect speech start and end
**And** VAD SHALL trigger STT processing

#### Scenario: Local turn detection
**Given** conversation is active
**When** turn detection runs
**Then** turn detection SHALL run locally
**And** turn detection SHALL identify when user has finished speaking
**And** turn detection SHALL trigger LLM processing

---

### Requirement: Pipeline Architecture
The system SHALL construct a Pipecat pipeline with custom processors for journey and guideline control.

#### Scenario: Pipeline construction
**Given** an incoming call
**When** pipeline is built
**Then** pipeline SHALL consist of: SIP Transport → Local VAD → DeepgramSTTService → Local Turn Detection → JourneyProcessor → OpenAILLMService → ValidatorProcessor → OpenAITTSService → SIP Transport
**And** all processors SHALL be async
**And** frames SHALL flow in defined order

#### Scenario: Journey-aware processing
**Given** user message enters pipeline
**When** JourneyProcessor handles frame
**Then** active journey context SHALL be retrieved from Redis/database
**And** if no active journey, activation SHALL be attempted via LLM
**And** current state guidance SHALL be injected into system prompt
**And** applicable guidelines SHALL be matched and included

#### Scenario: Response validation
**Given** LLM generates response
**When** ValidatorProcessor handles frame
**Then** response SHALL be validated against active guidelines
**And** violations SHALL be detected via LLM structured output
**And** if invalid, auto-fix SHALL be attempted
**And** validation results SHALL be logged to database

---

### Requirement: SIP Integration
The system SHALL integrate with sip-to-ai library for SIP/RTP audio transport via a custom Pipecat transport layer.

#### Scenario: Custom transport layer
**Given** Pipecat pipeline needs SIP connectivity
**When** custom transport is created
**Then** transport SHALL be implemented in `app/telephony/sip_transport.py`
**And** transport SHALL wrap sip-to-ai RTP streams
**And** transport SHALL convert RTP audio to/from Pipecat audio frames
**And** transport SHALL be project-specific (not a reusable library)

#### Scenario: SIP server initialization
**Given** application starts
**When** SIP server initializes
**Then** server SHALL listen on 0.0.0.0:5060
**And** INVITE from any IP SHALL be accepted (no auth for MVP)
**And** G.711 μ-law codec SHALL be negotiated
**And** server SHALL route incoming calls to Pipecat pipeline via custom transport

#### Scenario: Audio streaming
**Given** active SIP call
**When** audio flows
**Then** incoming RTP SHALL be decoded to PCM16 and forwarded to Pipecat
**And** outgoing Pipecat audio SHALL be encoded to G.711 and sent via RTP
**And** audio frames SHALL be 20ms chunks

#### Scenario: Call termination
**Given** call in progress
**When** caller sends BYE or hangs up
**Then** Pipecat pipeline SHALL terminate gracefully
**And** call metadata SHALL be persisted: duration, journeys, tools called
**And** cleanup SHALL complete within 2 seconds

---

### Requirement: Performance Target
The system SHALL achieve end-to-end response latency of <520ms (P50) from user speech end to audio response start.

#### Scenario: Latency measurement
**Given** user completes speaking
**When** system generates response
**Then** P50 latency SHALL be <520ms
**And** P95 latency SHALL be <800ms
**And** P99 latency SHALL be <1200ms

#### Scenario: Latency breakdown
**Given** components are measured
**When** profiling occurs
**Then** STT SHALL target ~100ms
**And** journey matching SHALL target ~30ms (cache hit <5ms)
**And** guideline matching SHALL complete in <60ms (P95), target ~50ms (P50)
**And** LLM generation SHALL target ~200ms
**And** validation SHALL target ~30ms
**And** TTS SHALL target ~100ms
