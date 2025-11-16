# AI 编程提示词：AI-Native Call Center

## 项目概述

**项目名称**: `ai-native-callcenter`

**核心理念**: 借鉴 Parlant 的 Journey + Guideline 思路，但采用原生实现以优化实时语音场景的性能

---

## 1️⃣ 明确的目标

### 项目目标

使用 **Pipecat + 原生流程控制引擎 + 开源技术栈**，完全重写现有的 Azure Call Center AI 系统。

**核心目标**：
- ✅ **流程可控**：通过原生 Journey 引擎确保 AI 遵循业务流程，杜绝偏离
- ✅ **行为合规**：通过原生 Guideline 引擎强制执行业务规则和合规要求
- ✅ **决策透明**：借鉴 ARQ 思路，使用 OpenAI structured output 实现可解释的推理
- ✅ **超低延迟**：目标响应时间 <520ms（无 Parlant Server 往返开销）
- ✅ **成本优化**：使用开源技术栈，成本降低 75%
- ✅ **完全可观测**：LGTM Stack 提供全方位监控

**业务目标**：
- 保留现有所有功能：理赔管理、提醒系统、通话合成、知识库查询
- 支持 100+ 并发通话
- 99.9% 系统可用性
- 每个决策都可追溯审计

**关键设计决策**：
- ❌ **不使用** Parlant 库/服务（避免额外网络延迟）
- ✅ **借鉴** Parlant 的 Journey、Guideline、ARQ 设计思路
- ✅ **原生实现** 轻量级状态机和规则引擎，深度优化实时语音场景

---

## 2️⃣ 技术栈

### **电话层（Telephony）**
```yaml
技术: sip-to-ai (纯Python异步SIP/RTP实现)
语言: Python 3.12+
特点:
  - 纯Python实现，无C依赖
  - asyncio异步架构
  - G.711 μ-law @ 8kHz
  - 低延迟 <50ms
参考: /Users/yangxionghui/workspaces/sip-to-ai
```

### **AI Pipeline层**
```yaml
框架: Pipecat 0.0.94+
用途: 实时语音AI pipeline编排
组件:
  - STT: Deepgram Nova-3 (WebSocket原生实现)
  - LLM: OpenAI GPT-4o (HTTP原生实现，带function calling)
  - TTS: OpenAI TTS (WebSocket原生实现)
架构: Frame-based pipeline
集成方式: 使用原生 HTTP/WebSocket 协议，无SDK依赖
参考: /Users/yangxionghui/workspaces/pipecat
```

### **流程控制层（原生实现）**
```yaml
设计: 借鉴 Parlant 思路，原生实现
核心组件:
  - Journey Engine: 轻量级状态机引擎
  - Guideline Engine: 快速规则匹配引擎
  - Validator: ARQ-inspired 响应验证
  - Tool Executor: 直接集成工具调用
优势:
  - 零额外延迟（无外部服务往返）
  - 深度优化（针对实时语音）
  - 完全可控（所有代码在手）
参考思路: /Users/yangxionghui/workspaces/parlant
```

### **数据层（开源）**
```yaml
数据库:
  - PostgreSQL 18 (主数据库)
  - 特性: 分区表、全文搜索(pg_trgm)、JSONB、UUID v7主键

缓存:
  - Redis 8
  - 用途: 工具调用结果缓存、会话状态、Pub/Sub
  - 特性: Streams (消息队列)

对象存储:
  - MinIO
  - 用途: 通话录音、提示词库、静态资源
```

### **可观测层（LGTM Stack）**
```yaml
组件:
  - Loki: 日志聚合
  - Grafana: 可视化仪表盘
  - Tempo: 分布式链路追踪
  - Mimir: 指标存储（或Prometheus）
  - Grafana Agent: 统一遥测采集

集成: OpenTelemetry (traces + metrics + logs)
```

### **Web框架**
```yaml
API: FastAPI 0.121.2+
服务器: Uvicorn (ASGI)
认证: JWT
WebSocket: 实时事件流
```

### **依赖清单**
```toml
# pyproject.toml
[project]
name = "ai-native-callcenter"
version = "2.0.0"
requires-python = ">=3.12"

dependencies = [
    # AI & Voice
    "pipecat-ai>=0.0.94",             # Pipecat pipeline框架
    # 使用原生 HTTP/WebSocket 与 OpenAI/Deepgram 通信，无SDK依赖

    # Web
    "fastapi>=0.121.2",
    "uvicorn>=0.38.0",
    "websockets>=15.0",

    # Database
    "asyncpg>=0.30.0",
    "redis>=7.0.1",
    "minio>=7.2.15",                  
    "alembic>=1.17.2",

    # Observability
    "opentelemetry-api>=1.38.0",      
    "opentelemetry-sdk>=1.38.0",
    "opentelemetry-instrumentation-fastapi",
    "opentelemetry-instrumentation-asyncpg",
    "opentelemetry-exporter-otlp>=1.38.0",
    "prometheus-client>=0.21.1",
    "structlog>=24.5.0",

    # Utils
    "pydantic>=2.12.4",
    "python-dotenv>=1.1.0",
    "apscheduler>=3.11.0",
]

```

---

## 3️⃣ 设计思路和框架

### **整体架构设计**

```
┌───────────────────────────────────────────────────────────────┐
│                     呼叫入口 (SIP Network)                     │
└─────────────────────────┬─────────────────────────────────────┘
                          │ SIP/RTP
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ 电话层 (sip-to-ai)                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │ SIP Server │→│ RTP Session│→│AudioAdapter│              │
│  └────────────┘  └────────────┘  └──────┬─────┘              │
└───────────────────────────────────────────┼───────────────────┘
                                            ↓ PCM16 8kHz
┌───────────────────────────────────────────────────────────────┐
│ AI Pipeline层 (Pipecat + 原生流程控制)                         │
│  ┌────────┐  ┌──────────────────────────┐  ┌────────┐        │
│  │  STT   │→→│  Journey-Aware LLM      │→→│  TTS   │        │
│  │Deepgram│  │  - State Machine        │  │ OpenAI │        │
│  └────────┘  │  - Guideline Matcher    │  └────────┘        │
│              │  - Tool Executor        │                     │
│              │  - Response Validator   │                     │
│              └──────────┬───────────────┘                    │
└─────────────────────────┼──────────────────────────────────┘
                          │
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ 原生流程控制引擎 (Parlant-Inspired Native Engine)              │
│  ┌─────────────────┐  ┌─────────────────┐                    │
│  │ Journey Engine  │  │ Guideline Engine│                    │
│  │ - State Graph   │  │ - Rule Matcher  │                    │
│  │ - Transitions   │  │ - Priority Mgmt │                    │
│  │ - Context Mgmt  │  │ - Fast Indexing │                    │
│  └────────┬────────┘  └────────┬────────┘                    │
│           │                    │                              │
│           └────────┬───────────┘                              │
│                    ↓                                          │
│           ┌─────────────────┐                                │
│           │ Validation Layer│ (ARQ-inspired)                 │
│           │ - Pre-check     │                                │
│           │ - Post-verify   │                                │
│           └────────┬────────┘                                │
└────────────────────┼─────────────────────────────────────────┘
                     │
                     ↓
┌───────────────────────────────────────────────────────────────┐
│ 业务逻辑层 (Tool Implementation)                               │
│  Claims Service │ Customer Service │ Knowledge Service        │
└────────────────────┬──────────────────────────────────────────┘
                     ↓
┌───────────────────────────────────────────────────────────────┐
│ 数据层 (PostgreSQL 18 + Redis 8 + MinIO)                      │
└───────────────────────────────────────────────────────────────┘
```

### **核心设计思路**

#### **1. 分层架构原则**

**职责清晰**：
- **电话层**：只负责 SIP/RTP 协议处理和音频编解码
- **Pipeline层**：只负责 STT/TTS 和音频流管道
- **控制层**：负责对话流程控制和规则执行（原生实现）
- **业务层**：负责具体业务逻辑实现（Tool实现）
- **数据层**：负责数据持久化和缓存

**依赖方向**：
```
电话层 → Pipeline层 → 控制层 → 业务层 → 数据层
(单向依赖，上层不知道下层实现细节)
```

#### **2. Journey 引擎设计（原生实现）**

**核心概念**（借鉴 Parlant）：
```python
Journey = 有向图 (DAG)
  - Node = State (chat_state | tool_state | fork_state)
  - Edge = Transition (direct | conditional)

设计原则:
  1. 每个业务流程 = 1个Journey
  2. State描述"做什么"，不描述"怎么做"
  3. Transition条件要明确、可验证
  4. 允许跳过/回退，但记录偏离
  5. 所有定义存储在PostgreSQL，运行时缓存在Redis
```

**数据模型**：
```python
@dataclass
class JourneyState:
    id: str
    type: StateType  # CHAT, TOOL, FORK, END
    action: Optional[str]        # chat状态的指导语
    tools: List[str]             # tool状态要调用的工具
    metadata: Dict[str, Any]

@dataclass
class JourneyTransition:
    source_state: str
    target_state: str
    condition: Optional[str]     # 转换条件（自然语言）
    priority: int

@dataclass
class Journey:
    id: str
    name: str
    description: str
    activation_conditions: List[str]  # 激活条件
    states: Dict[str, JourneyState]
    transitions: List[JourneyTransition]
    initial_state: str

@dataclass
class JourneyContext:
    journey_id: str
    session_id: str
    current_state: str
    state_history: List[str]
    variables: Dict[str, Any]
    activated_at: float
```

**核心逻辑**：
- **激活判断**：LLM + structured output 判断用户意图是否匹配 activation_conditions
- **状态指导**：当前状态的 action 字段注入到 system prompt
- **状态转换**：LLM 判断 transition conditions 是否满足
- **性能优化**：Redis 缓存激活判断结果、状态定义

#### **3. Guideline 引擎设计（原生实现）**

**核心概念**（借鉴 Parlant）：
```python
Guideline = (Condition, Action, Tools)

分类:
  1. 全局规则: 适用所有对话
     - 身份验证
     - 数据隐私
     - 转人工条件

  2. Journey规则: 特定流程内
     - 状态前置条件
     - 业务验证逻辑

  3. State规则: 特定状态内
     - 状态特定约束

优先级: State规则 > Journey规则 > 全局规则
```

**数据模型**：
```python
@dataclass
class Guideline:
    id: str
    scope: GuidelineScope  # GLOBAL, JOURNEY, STATE
    scope_id: Optional[str]

    condition: str          # 触发条件（自然语言）
    action: Optional[str]   # 执行动作（自然语言）
    tools: List[str]        # 需要调用的工具

    priority: int
    enabled: bool

    # 性能优化字段
    keywords: List[str]     # 关键词（快速预筛选）
    metadata: Dict[str, Any]
```

**匹配流程**（两阶段，优化延迟）：
```
1. 关键词预筛选 (< 5ms)
   - 提取消息关键词
   - 匹配 guideline.keywords
   - 过滤掉 90% 不相关规则

2. LLM 精确匹配 (< 50ms)
   - 批量判断候选规则
   - structured output
   - 返回适用规则列表

总延迟: < 60ms
```

#### **4. 响应验证器（ARQ-Inspired）**

**核心思路**（借鉴 Parlant ARQ）：
- 不依赖 Parlant 的 ARQ 框架
- 使用 OpenAI structured output 实现类似效果
- 验证 LLM 响应是否符合激活的 Guidelines

**验证流程**：
```python
1. Pre-validation（请求前）
   - 检查 Journey 状态是否允许
   - 检查必要 Guideline 是否满足

2. Post-validation（响应后）
   - 验证响应是否违反 Guidelines
   - 使用 structured output 获取验证结果
   - 如违规，自动修正或重新生成

3. Audit Trail（审计追踪）
   - 记录所有验证过程
   - 存储到 PostgreSQL
   - 关联到 session/call
```

**实现**：
```python
async def validate_response(
    proposed_response: str,
    active_guidelines: List[Guideline],
    journey_context: Optional[JourneyContext]
) -> Dict[str, Any]:
    """验证响应是否符合规则"""

    prompt = f"""
    验证以下AI响应是否符合业务规则：

    AI响应: {proposed_response}

    必须遵守的规则：
    {format_guidelines(active_guidelines)}

    返回JSON：
    {{
        "is_valid": bool,
        "violations": [{{"rule": str, "reason": str}}],
        "suggested_fixes": [str],
        "confidence": float
    }}
    """

    result = await llm.structured_completion(prompt, schema)
    return result
```

#### **5. Tool Calling 设计（替代 RAG）**

**为什么不用 RAG**：
- ❌ 延迟高：embedding生成 + 向量搜索 = 200-500ms
- ❌ 不准确：语义相似 ≠ 真正相关
- ❌ 上下文污染：检索内容可能无关

**Tool Calling 优势**：
- ✅ 延迟低：PostgreSQL 查询 <50ms
- ✅ 精确性：LLM 主动决定何时需要什么信息
- ✅ 可缓存：Redis 缓存常见查询结果

**知识库设计**（非向量方式）：
```sql
-- 结构化知识库
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),  -- UUID v7主键
    category VARCHAR(100),      -- 分类索引
    keywords TEXT[],            -- 关键词数组
    question TEXT,
    answer TEXT,
    priority INTEGER,
    -- 全文搜索（非向量）
    search_vector tsvector GENERATED ALWAYS AS
        (to_tsvector('english', question || ' ' || answer)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引策略
CREATE INDEX idx_kb_category ON knowledge_base(category);
CREATE INDEX idx_kb_keywords ON knowledge_base USING gin(keywords);
CREATE INDEX idx_kb_search ON knowledge_base USING gin(search_vector);
CREATE INDEX idx_kb_created ON knowledge_base(created_at);

-- 查询策略：
-- 1. 先查 Redis 缓存 (< 5ms)
-- 2. 分类+关键词精确匹配 (< 20ms)
-- 3. 全文搜索 fallback (< 50ms)
```

**工具定义**：
```python
@tool
async def search_knowledge_base(
    context: ToolContext,
    category: str,
    query: str
) -> ToolResult:
    """搜索知识库（快速结构化搜索，非向量）"""

    # 1. Redis 缓存
    cache_key = f"kb:{category}:{query[:50]}"
    cached = await context.redis.get(cache_key)
    if cached:
        return ToolResult(data=json.loads(cached))

    # 2. PostgreSQL 全文搜索
    result = await context.db.fetchrow("""
        SELECT question, answer
        FROM knowledge_base
        WHERE category = $1
          AND search_vector @@ plainto_tsquery('english', $2)
        ORDER BY ts_rank(...) DESC
        LIMIT 1
    """, category, query)

    # 3. 缓存结果
    if result:
        data = {"found": True, "answer": result['answer']}
        await context.redis.setex(cache_key, 1800, json.dumps(data))
        return ToolResult(data=data)

    return ToolResult(data={"found": False})
```

#### **6. Pipecat 集成设计**

**核心思路**：
- 使用自定义 FrameProcessor 拦截 LLM 消息
- 注入 Journey 状态指导和 Guideline 规则
- 验证 LLM 响应

**实现**：
```python
class JourneyAwareProcessor(FrameProcessor):
    """Journey 感知的处理器"""

    async def process_frame(self, frame, direction):
        if isinstance(frame, LLMMessagesFrame):
            # 1. 提取用户消息
            user_message = frame.messages[-1]['content']

            # 2. Journey 控制
            active_journey = await self.get_active_journey()
            if not active_journey:
                active_journey = await self.try_activate_journey(user_message)

            state_guidance = None
            if active_journey:
                state_guidance = await self.journey_engine.get_current_state_guidance(
                    active_journey
                )

            # 3. Guideline 匹配
            matched_guidelines = await self.guideline_matcher.match_guidelines(
                user_message=user_message,
                active_journey=active_journey.journey_id if active_journey else None,
                current_state=active_journey.current_state if active_journey else None
            )

            # 4. 构建增强 Prompt
            system_prompt = self.build_enhanced_prompt(
                state_guidance=state_guidance,
                guidelines=matched_guidelines
            )

            # 5. 注入到消息
            enhanced_messages = [
                {"role": "system", "content": system_prompt},
                *frame.messages
            ]

            enhanced_frame = LLMMessagesFrame(messages=enhanced_messages)
            await self.push_frame(enhanced_frame, direction)

        elif isinstance(frame, TextFrame):
            # LLM 响应验证
            validation_result = await self.validator.validate_response(
                proposed_response=frame.text,
                active_guidelines=...,
                journey_context=...
            )

            if not validation_result['is_valid']:
                # 自动修正
                fixed = await self.validator.auto_fix_response(...)
                frame = TextFrame(text=fixed)

            await self.push_frame(frame, direction)

        else:
            await self.push_frame(frame, direction)
```

#### **7. 性能优化策略**

**延迟目标**：
```
目标: <520ms 端到端响应

延迟拆分:
  - STT (Deepgram):        ~100ms
  - Journey匹配:           ~30ms  (缓存命中 <5ms)
  - Guideline匹配:         ~50ms  (关键词预筛选 + 批量LLM)
  - LLM生成 (GPT-4o):      ~200ms (流式响应)
  - 响应验证:              ~30ms  (并行)
  - TTS (OpenAI):          ~100ms
  ================================
  总计:                    ~510ms

优化手段:
  1. 关键词预筛选（减少 90% 候选规则）
  2. Redis 缓存（Journey激活、Guideline匹配）
  3. 批量 LLM 调用（减少往返次数）
  4. 异步并行（验证与 TTS 准备并行）
  5. 流式响应（TTS 可提前开始）
```

**缓存策略**：
```python
CACHE_STRATEGY = {
    # L1: 热点数据（永久或长期）
    "journeys_definitions": "永久",
    "guidelines_enabled": "10分钟",
    "knowledge_common": "1小时",

    # L2: 会话数据（短期）
    "journey_context:{session_id}": "通话时长+1h",
    "guideline_match:{message_hash}": "5分钟",
    "tool_result:{tool}:{params_hash}": "30分钟",

    # L3: 计算结果（超短期）
    "llm_completion:{prompt_hash}": "5分钟",
}
```

#### **8. 监控与可观测**

**LGTM Stack 集成**：
```python
# Metrics (Prometheus/Mimir)
journey_activations = Counter('journey_activations_total', ['journey_name'])
guideline_matches = Counter('guideline_matches_total', ['guideline_id'])
tool_latency = Histogram('tool_latency_seconds', ['tool_name'])
e2e_latency = Histogram('response_latency_e2e_seconds')

# Logs (Loki via structlog)
logger.info("journey_activated",
    call_id=call_id,
    journey="claims_filing",
    trigger="customer_intent")

# Traces (Tempo via OpenTelemetry)
@tracer.start_as_current_span("process_call")
async def process_call(call_id):
    with tracer.start_as_current_span("journey_match"):
        ...
```

**关键指标**：
```yaml
业务指标:
  - Journey完成率
  - Guideline遵守率
  - 工具调用成功率
  - 人工转接率

技术指标:
  - 端到端延迟 (p50, p95, p99)
  - 各组件延迟 (Journey, Guideline, LLM, Tool)
  - 数据库连接池使用率
  - Redis缓存命中率

质量指标:
  - 对话偏离次数
  - 验证失败次数
  - 合规违规次数
```

---

## 📁 项目结构

```
ai-native-callcenter/
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── telephony/                  # sip-to-ai 集成
│   │   ├── sip_server.py
│   │   ├── rtp_session.py
│   │   └── audio_adapter.py
│   │
│   ├── pipeline/                   # Pipecat pipeline
│   │   ├── factory.py
│   │   ├── transports/
│   │   │   └── sip_transport.py
│   │   ├── processors/
│   │   │   ├── journey_processor.py
│   │   │   └── guideline_processor.py
│   │   └── clients/                # 🆕 原生API客户端
│   │       ├── openai_client.py    # OpenAI HTTP/WS客户端
│   │       └── deepgram_client.py  # Deepgram WS客户端
│   │
│   ├── flow_control/               # 🆕 原生流程控制引擎
│   │   ├── __init__.py
│   │   │
│   │   ├── journey/                # Journey引擎
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # 状态机引擎核心
│   │   │   ├── models.py           # Journey数据模型
│   │   │   ├── store.py            # Journey存储
│   │   │   ├── matcher.py          # 条件匹配
│   │   │   └── definitions/        # Journey定义
│   │   │       ├── claims.py
│   │   │       ├── appointment.py
│   │   │       └── inquiry.py
│   │   │
│   │   ├── guideline/              # Guideline引擎
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # 规则引擎核心
│   │   │   ├── models.py           # Guideline数据模型
│   │   │   ├── matcher.py          # 规则匹配器（快速）
│   │   │   ├── priority.py         # 优先级管理
│   │   │   └── definitions/        # Guideline定义
│   │   │       ├── compliance.py
│   │   │       ├── identity.py
│   │   │       └── handoff.py
│   │   │
│   │   ├── validator/              # 验证层（ARQ-inspired）
│   │   │   ├── __init__.py
│   │   │   ├── pre_validator.py
│   │   │   ├── post_validator.py
│   │   │   └── schemas.py
│   │   │
│   │   └── context.py              # 会话上下文管理
│   │
│   ├── tools/                      # Tool Calling实现
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── executor.py
│   │   ├── customer_tools.py
│   │   ├── claims_tools.py
│   │   └── knowledge_tools.py
│   │
│   ├── business/                   # 业务逻辑
│   │   ├── claims_service.py
│   │   ├── customer_service.py
│   │   └── knowledge_service.py
│   │
│   ├── persistence/                # 数据访问
│   │   ├── database.py
│   │   ├── cache.py
│   │   ├── storage.py
│   │   └── repositories/
│   │
│   ├── api/                        # FastAPI
│   │   ├── routes/
│   │   │   ├── calls.py
│   │   │   ├── journeys.py
│   │   │   ├── guidelines.py
│   │   │   └── admin.py
│   │   └── websocket.py
│   │
│   ├── monitoring/                 # LGTM Stack
│   │   ├── metrics.py
│   │   ├── tracing.py
│   │   └── logging.py
│   │
│   ├── models/
│   │   ├── call.py
│   │   ├── claim.py
│   │   └── session.py
│   │
│   └── config/
│       ├── settings.py
│       └── prompts.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── migrations/
│   ├── versions/
│   └── seed_data/
│
├── scripts/                        # 🆕 部署和运维脚本
│   ├── deploy.sh
│   ├── migrate.sh
│   ├── seed_knowledge.py
│   └── backup.sh
│
├── docs/                           # 🆕 文档
│   ├── api/
│   │   └── openapi.yaml
│   ├── architecture/
│   │   ├── system_design.md
│   │   └── diagrams/
│   └── guides/
│       ├── journey_guide.md
│       └── guideline_guide.md
│
├── examples/                       # 🆕 示例代码
│   ├── simple_call.py
│   ├── custom_journey.py
│   └── tool_integration.py
│
├── monitoring/
│   ├── grafana/
│   └── prometheus/
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── pyproject.toml
└── README.md
```

---

## 🚀 实施步骤

### **Step 1: 环境准备**
```bash


# 1. 初始化Python项目
uv init --python 3.12

# 2. 启动基础设施
docker-compose up -d postgres redis minio

# 3. 初始化数据库
psql -h localhost -U admin -d callcenter -f migrations/init.sql
```

### **Step 2: Journey 引擎开发**
```python
# 1. 定义数据模型 (app/flow_control/journey/models.py)
# 2. 实现状态机引擎 (app/flow_control/journey/engine.py)
# 3. 实现条件匹配器 (app/flow_control/journey/matcher.py)
# 4. 定义业务Journey (app/flow_control/journey/definitions/)
# 5. 单元测试
```

### **Step 3: Guideline 引擎开发**
```python
# 1. 定义数据模型 (app/flow_control/guideline/models.py)
# 2. 实现规则匹配器 (app/flow_control/guideline/matcher.py)
# 3. 实现优先级管理 (app/flow_control/guideline/priority.py)
# 4. 定义业务规则 (app/flow_control/guideline/definitions/)
# 5. 性能测试（关键词预筛选效果）
```

### **Step 4: 验证器开发**
```python
# 1. 实现响应验证器 (app/flow_control/validator/post_validator.py)
# 2. 实现自动修正逻辑
# 3. 设计验证 schema
# 4. 集成测试
```

### **Step 5: Tool 实现**
```python
# 1. 核心业务工具（身份验证、理赔CRUD）
# 2. 知识查询工具（替代RAG）
# 3. 辅助工具（提醒、转接）
# 4. 每个工具都要：
#    - 清晰的文档说明（LLM依赖这个）
#    - 参数验证
#    - 错误处理
#    - 缓存策略
#    - 监控指标
```

### **Step 6: Pipecat 集成**
```python
# 1. 实现 JourneyAwareProcessor
# 2. 集成 Journey 引擎
# 3. 集成 Guideline 匹配器
# 4. 集成 Validator
# 5. 端到端测试
```

### **Step 7: 监控集成**
```python
# 1. 配置 LGTM Stack
# 2. 添加关键指标
# 3. 创建 Grafana 仪表盘
# 4. 配置告警规则
```

### **Step 8: 性能优化**
```python
# 1. 负载测试
# 2. 延迟分析
# 3. 缓存优化
# 4. 数据库查询优化
# 5. 达到 <520ms 目标
```

---

## ⚠️ 关键注意事项

1. **不使用 Parlant 库，但借鉴思路**
   - Journey 概念 → 自研轻量级状态机
   - Guideline 概念 → 自研规则引擎
   - ARQ 思路 → OpenAI structured output

2. **性能优先**
   - 目标：<520ms 端到端响应
   - 关键词预筛选（90% 过滤）
   - Redis 多层缓存
   - 批量 LLM 调用

3. **Tool Calling 不是 RAG**
   - 不做实时向量搜索
   - 使用 PostgreSQL 全文搜索 + 关键词
   - 结果缓存到 Redis

4. **异步是核心**
   - 所有 I/O 操作必须 async/await
   - 数据库、Redis、MinIO 都要异步

5. **监控先行**
   - 从第一天就集成 LGTM Stack
   - 每个操作都要记录指标
   - 决策链路必须可追溯

6. **降级策略**
   - Journey 引擎故障 → 直接 LLM（无控制）
   - LLM 故障 → 固定话术
   - DB 故障 → 只读模式

---

## 📋 开发计划（16周）

### **Phase 1: 基础设施 (Week 1-2)**
- PostgreSQL 18 + Redis 8 + MinIO + LGTM Stack
- 数据库 schema（journeys, guidelines 表）

### **Phase 2: 电话层 (Week 3-4)**
- sip-to-ai 集成
- Pipecat 基础 pipeline

### **Phase 3: Journey 引擎 (Week 5-6)**
- Journey 数据模型
- 状态机引擎实现
- 条件匹配逻辑
- Journey 定义（理赔、预约、咨询）

### **Phase 4: Guideline 引擎 (Week 7-8)**
- Guideline 数据模型
- 关键词预筛选
- LLM 批量匹配
- Guideline 定义（合规、业务）

### **Phase 5: 验证层 + Tool (Week 9-10)**
- 响应验证器（ARQ-inspired）
- 自动修正逻辑
- Tool 实现（客户、理赔、知识库）

### **Phase 6: Pipeline 集成 (Week 11-12)**
- JourneyAwareProcessor 实现
- 完整流程打通
- 性能优化

### **Phase 7: 监控与测试 (Week 13-15)**
- LGTM Stack 集成
- 负载测试
- 延迟优化

### **Phase 8: 部署 (Week 16)**
- 生产环境部署
- 灰度发布

---

## 💡 核心优势

| 特性 | 使用 Parlant 库 | 原生实现 |
|-----|----------------|---------|
| **Journey** | Parlant Server | 轻量级状态机 |
| **Guideline** | Parlant Engine | 快速规则引擎 |
| **ARQ** | Parlant 内置 | OpenAI structured output |
| **延迟** | ~800ms | <520ms |
| **可控性** | 中 | 高 |
| **优化空间** | 小 | 大 |
| **依赖** | Parlant + OpenAI/Deepgram SDK | 原生 HTTP/WebSocket |

**总结**：
- ✅ 保留 Parlant 优秀的设计思路
- ✅ 去除外部服务依赖，降低延迟
- ✅ 深度优化实时语音场景
- ✅ 完全掌控代码，灵活调整
