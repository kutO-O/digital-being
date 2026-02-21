# 🤝 Multi-Agent Communication System

## Overview

Stage 27 implements a multi-agent system where multiple Digital Being instances can communicate, collaborate, and share knowledge.

## Architecture

```
┌─────────────────────────────────────────────┐
│         Agent Network Manager               │
│  (Discovery, Registry, Message Routing)     │
└─────────────────────────────────────────────┘
           │         │          │
    ┌──────┴───┐  ┌──┴────┐  ┌─┴──────┐
    │ Agent A  │  │Agent B│  │Agent C │
    │(Research)│  │(Code) │  │(Test)  │
    └──────────┘  └───────┘  └────────┘
```

## Components

### 1. MessageProtocol (`core/message_protocol.py`)

**Purpose**: Defines structured messages for agent communication.

**Message Types**:
- `QUERY` - Ask another agent for information
- `RESPONSE` - Reply to a query
- `TASK` - Delegate a task
- `STATUS` - Status update
- `SKILL_SHARE` - Share a skill
- `CONSENSUS` - Request vote
- `VOTE` - Cast a vote
- `BROADCAST` - Send to all
- `HEARTBEAT` - Alive signal

**Priority Levels**:
- `CRITICAL` (3) - Must process immediately
- `HIGH` (2) - Process soon
- `NORMAL` (1) - Default priority
- `LOW` (0) - Process when idle

**Example**:
```python
from core.message_protocol import MessageBuilder

# Send query
message = MessageBuilder.query(
    from_agent="alice",
    to_agent="bob",
    question="What's the best Python web framework?",
    context={"use_case": "REST API"}
)
```

### 2. AgentRegistry (`core/agent_registry.py`)

**Purpose**: Tracks all agents in the network.

**Features**:
- Agent registration/unregistration
- Heartbeat monitoring
- Find agents by specialization
- Load balancing (find least busy agent)
- Automatic cleanup of stale agents

**Example**:
```python
registry.register(
    agent_id="alice_123",
    name="Alice",
    specialization="research",
    host="localhost",
    port=9000
)

# Find best agent for task
agent = registry.get_best_for_task("coding")
```

### 3. MessageBroker (`core/message_broker.py`)

**Purpose**: Message queue and routing.

**Features**:
- Priority-based message queues
- Async message delivery
- Wait for replies with timeout
- Message persistence (JSONL format)
- Handler registration by message type

**Example**:
```python
# Send and wait for reply
msg_id = broker.send(query_message)
reply = await broker.wait_for_reply(msg_id, timeout=30.0)

# Register handler
def handle_query(message):
    print(f"Received: {message.payload}")

broker.register_handler(MessageType.QUERY, handle_query)
```

### 4. SkillExchange (`core/skill_exchange.py`)

**Purpose**: Share and import skills between agents.

**Features**:
- Export skills from SkillLibrary
- Import skills from other agents
- Trust-based confidence adjustment
- Skill source tracking

**Example**:
```python
# Share skill
skill_exchange.share_skill(skill_id="fastapi_endpoint", to_agent="*")

# Update trust after successful skill use
skill_exchange.update_trust(agent_id="bob", delta=+0.1)
```

### 5. MultiAgentCoordinator (`core/multi_agent_coordinator.py`)

**Purpose**: Main interface for multi-agent operations.

**Features**:
- Send queries and wait for responses
- Delegate tasks to specialized agents
- Share skills with network
- Request consensus votes
- Broadcast announcements

## Configuration

Add to `config.json`:

```json
{
  "multi_agent": {
    "enabled": true,
    "agent_name": "alice",
    "specialization": "research",
    "network": {
      "host": "localhost",
      "port": 9000,
      "discovery_port": 9001
    },
    "auto_register": true
  }
}
```

## Usage Examples

### Starting Multiple Agents

```bash
# Terminal 1 - Research agent
python main.py --agent-name alice --specialization research --port 9000

# Terminal 2 - Coding agent
python main.py --agent-name bob --specialization coding --port 9001

# Terminal 3 - Testing agent
python main.py --agent-name charlie --specialization testing --port 9002
```

### Sending Queries

```python
# Alice asks Bob
answer = await coordinator.send_query_and_wait(
    to_agent="bob",
    question="How do I create a FastAPI endpoint?",
    context={"framework": "FastAPI"},
    timeout=30.0
)
print(f"Bob's answer: {answer}")
```

### Task Delegation

```python
# Alice delegates to Bob
task_id = coordinator.delegate_task(
    task="Create /health endpoint",
    context={
        "type": "coding",
        "framework": "FastAPI",
        "requirements": ["return server status", "include timestamp"]
    },
    priority=Priority.HIGH
)

# Coordinator automatically finds best coding agent
print(f"Task delegated: {task_id}")
```

### Skill Sharing

```python
# Bob shares his FastAPI skill
coordinator.share_skill(skill_id="fastapi_endpoint_creation", to_agent="*")

# All agents receive and import the skill (with trust adjustment)
```

### Consensus Voting

```python
# Alice requests consensus
result = await coordinator.request_consensus(
    question="Which database should we use?",
    options=["PostgreSQL", "MongoDB", "SQLite"],
    timeout=30
)

print(f"Consensus: {result}")
# Output: Consensus: PostgreSQL (2/3 votes)
```

### Broadcasting

```python
# Announce to all agents
coordinator.broadcast(
    announcement="New version deployed",
    data={"version": "2.0.0", "restart_required": False}
)
```

## API Endpoints

### `GET /agents`
List all registered agents.

**Response**:
```json
{
  "agents": [
    {
      "agent_id": "alice_123",
      "name": "Alice",
      "specialization": "research",
      "status": "online",
      "load": 0.3
    }
  ],
  "total": 3,
  "online": 3
}
```

### `GET /messages`
Get message queue.

**Response**:
```json
{
  "queue_sizes": {
    "CRITICAL": 0,
    "HIGH": 2,
    "NORMAL": 5,
    "LOW": 1
  },
  "total_queued": 8
}
```

### `POST /send`
Send message to agent.

**Request**:
```json
{
  "to_agent": "bob",
  "type": "query",
  "payload": {
    "question": "What's 2+2?"
  }
}
```

### `GET /skills/shared`
View shared skills.

**Response**:
```json
{
  "shared_skills": [
    {
      "id": "skill_123",
      "name": "FastAPI endpoint creation",
      "source_agent": "bob",
      "confidence": 0.85
    }
  ],
  "total": 5
}
```

## Specialization Types

- **research** - Information gathering, web search, analysis
- **coding** - Code generation, refactoring, debugging
- **testing** - Test creation, validation, QA
- **planning** - Task breakdown, strategy, coordination
- **general** - General-purpose agent

## Trust System

Agents build trust based on skill performance:

- **Initial trust**: 0.5 (neutral)
- **Successful skill use**: +0.1 trust
- **Failed skill use**: -0.15 trust
- **Trust affects confidence**: `adjusted_confidence = skill_confidence * trust_score`

## Message Flow Example

```
Alice (Research)                    Bob (Coding)
    |
    | QUERY: "Best web framework?"
    |────────────────────────────────>
    |                                  |
    |                                  | (processes query)
    |                                  |
    |      RESPONSE: "FastAPI"         |
    <─────────────────────────────────
    |
    | TASK: "Create /health endpoint"
    |────────────────────────────────>
    |                                  |
    |       STATUS: "accepted"         |
    <─────────────────────────────────
    |                                  |
    |                                  | (completes task)
    |                                  |
    |       STATUS: "completed"        |
    <─────────────────────────────────
    |
```

## Best Practices

1. **Use specialization** - Assign clear roles to agents
2. **Send heartbeats** - Keep registry updated
3. **Set timeouts** - Don't wait forever for replies
4. **Priority wisely** - Don't mark everything as CRITICAL
5. **Trust gradually** - Build trust through successful interactions
6. **Broadcast sparingly** - Avoid spam to all agents

## Troubleshooting

**No agents found for task**:
- Check if agents are registered: `GET /agents`
- Verify specializations match task type
- Ensure agents are sending heartbeats

**Messages not received**:
- Check message queues: `GET /messages`
- Verify agent IDs are correct
- Check if messages expired (TTL)

**Consensus timeout**:
- Increase timeout duration
- Check if enough agents are online
- Verify agents are responding to CONSENSUS messages

## Future Enhancements

- 📡 Network discovery (UDP broadcast)
- 🔐 Encrypted communication
- 🎯 Load balancing strategies
- 📈 Performance monitoring dashboard
- 🤝 Agent reputation system
- 📝 Conversation history between agents
