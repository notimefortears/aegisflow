# AegisFlow

**Self-hosted workflow automation with built-in security**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](./docker-compose.yml)

---

## Overview

AegisFlow combines a visual workflow editor with execution tracking, credential storage, role-based access, and security checks. Workflows can call external providers, receive webhooks, transform data, and pause for human approval.

Provider inputs can be scanned for sensitive information and prompt injection before dispatch. External providers receive the inputs sent to them; workflow state and audit records are stored in your deployment.

## Key Features

### Visual Workflow Builder
Drag-and-drop canvas powered by React Flow. Connect nodes, configure them inline, and run workflows in real time — no YAML required.

### 15+ Built-in Nodes
| Node | Description |
|------|-------------|
| **Claude** | Anthropic Claude (Opus, Sonnet, Haiku) with streaming |
| **OpenAI** | GPT-4o, o1, and any compatible endpoint |
| **HTTP Request** | Arbitrary REST calls with auth templates |
| **Webhook Trigger** | Receive inbound HTTP events |
| **Schedule Trigger** | Cron-based workflow scheduling |
| **PostgreSQL** | Parameterized queries against any Postgres instance |
| **Email** | Send transactional email via SMTP |
| **If / Switch** | Conditional branching |
| **Code** | Execute sandboxed Python snippets |
| **Set / Transform** | Map and reshape data between nodes |
| **Merge** | Join parallel branches |
| **Wait** | Delay or wait for external event |
| **Human Gate** | Pause for manual approval (see below) |
| **PII Scanner** | Explicit PII check node for inline use |
| **Sub-workflow** | Invoke another workflow as a reusable step |

### Built-in PII Detection
Every automated node call is automatically scanned before the prompt is dispatched. Detected PII (names, emails, SSNs, credit card numbers, etc.) is handled according to your policy:

- **Block** — reject the step and fail the execution
- **Redact** — replace detected entities with tokens before sending, restore in output
- **Alert** — log the event and continue

Configurable per-workflow or globally via `MAX_PII_RISK_SCORE`.

### Prompt Injection Protection
A pattern + heuristic scoring engine evaluates every text input that flows into an automated node. Scores above `MAX_INJECTION_RISK_SCORE` are blocked, logged, and surfaced in the audit trail. Common attack vectors (role override, instruction leakage, jailbreak templates) are detected out of the box; you can add custom rules.

### Human-in-the-Loop Gates
Insert a **Human Gate** node anywhere in a workflow. Execution pauses, the assigned reviewer receives a notification, and they approve or reject via the web UI. The full decision — who, when, what they saw — is recorded. Ideal before irreversible actions: sending bulk email, writing to a production database, or executing generated code.

### Credential Vault
API keys and secrets are encrypted with AES-256 (Fernet) before being written to the database. They are never returned in API responses. Nodes reference credentials by name; the runtime resolves them at execution time only.

### Role-Based Access Control
Four built-in roles:

| Role | Can do |
|------|--------|
| **Admin** | Everything, including user and credential management |
| **Editor** | Create, edit, run workflows; manage own credentials |
| **Viewer** | Read-only access to workflows and execution history |
| **Runner** | Trigger workflows via API; cannot edit |

### Full Audit Trail
Every execution step, security event, human decision, and credential access is appended to an append-only audit log table. Configurable retention (`AUDIT_RETENTION_DAYS`). Export to JSON or stream to your SIEM.

### Real-time Execution View
WebSocket-powered live execution panel. Watch nodes light up as they run, see intermediate outputs, and stream automated responses character-by-character.

### Fully Self-hosted
One `docker compose up` and you are running. Postgres, Redis, Celery workers, and the web UI are all included. No external services required for core functionality.

---

## Quick Start

```bash
git clone https://github.com/notimefortears/aegisflow
cd aegisflow

# Copy and configure environment
cp .env.example .env

## Required: set these three values in .env
## SECRET_KEY              — random 64-char hex string
## CREDENTIAL_ENCRYPTION_KEY — 32-byte URL-safe base64 Fernet key
## INITIAL_ADMIN_PASSWORD  — your first admin password
## POSTGRES_PASSWORD       — postgres database password

make prod
```

Open [http://localhost](http://localhost) and log in with `admin@example.com` and the password you set.

> For HTTPS in production, mount your TLS certificates into `nginx/ssl/` as `fullchain.pem` and `privkey.pem` before starting.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              Browser                    │
                         └──────────────────┬──────────────────────┘
                                            │ HTTPS / WSS
                         ┌──────────────────▼──────────────────────┐
                         │               Nginx                     │
                         │  Rate limiting · TLS · Security headers │
                         └───────┬──────────────────┬──────────────┘
                                 │ /api             │ /
                    ┌────────────▼──────┐  ┌────────▼────────┐
                    │  FastAPI Backend  │  │  React Frontend │
                    │  (uvicorn x4)     │  │  (nginx static) │
                    └──────┬────────────┘  └─────────────────┘
                           │
              ┌────────────┼────────────────┐
              │            │                │
   ┌──────────▼───┐  ┌─────▼──────┐  ┌─────▼──────────────────────────┐
   │  PostgreSQL  │  │   Redis    │  │       Security Engine           │
   │  (state,     │  │  (cache,   │  │  PII Detection · Injection      │
   │  audit log)  │  │  pubsub)   │  │  Scoring · Policy Enforcement   │
   └──────────────┘  └─────┬──────┘  └─────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Celery    │
                    │  Workers    │
                    │ (async ops) │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
   ┌──────────▼──────┐       ┌──────────▼──────┐
   │  Claude (Anthropic)│    │  OpenAI / Other  │
   │  automated Node          │    │  automated Node         │
   └───────────────────┘    └──────────────────┘
```

---

## Security Model

### PII Detection
AegisFlow embeds a multi-strategy PII scanner that runs before every automated call:

- **Regex patterns**: SSN, credit cards, email addresses, phone numbers
- **Entity recognition**: names, addresses, dates of birth (rule-based NER)
- **Risk scoring**: composite 0–1 score; configurable threshold per workflow

### Injection Scoring
Inputs are scored for prompt injection risk using:

- Known jailbreak phrase matching
- Role-override heuristics (`ignore previous instructions`, `you are now`, etc.)
- Unusual token entropy patterns
- Nested instruction detection

Scores above the configured threshold (`MAX_INJECTION_RISK_SCORE`, default 0.7) are blocked before they reach the model.

### Policy Engine
Per-workflow security policies define:
- Which PII actions are allowed (block / redact / alert)
- Maximum injection risk threshold
- Whether human gates are required for sensitive node types
- Which roles can trigger the workflow

### Audit Trail
The audit log is append-only at the application level. Every record includes:
- Timestamp (microsecond precision)
- Workflow and execution ID
- User identity (JWT subject)
- Node type and input/output hash
- Security events (PII hits, injection blocks, human approvals)
- IP address and user agent

---

## Development Setup

```bash
## Start postgres, redis, hot-reload backend, and Vite dev server
make dev

## In another terminal — run the test suite
make test

## Lint and type check
make lint

## Auto-format
make format
```

The Vite dev server runs on [http://localhost:5173](http://localhost:5173) and proxies `/api` to the backend at `localhost:8000`. No nginx is involved in dev.

---

## Available Make Targets

| Target | Description |
|--------|-------------|
| `make dev` | Start development environment |
| `make prod` | Start production stack |
| `make down` | Stop all containers |
| `make logs` | Tail all service logs |
| `make db-migrate` | Run `alembic upgrade head` |
| `make db-rollback` | Run `alembic downgrade -1` |
| `make test` | Run pytest with coverage |
| `make lint` | ruff + mypy |
| `make format` | black + isort |
| `make build` | Rebuild Docker images |
| `make shell-backend` | Shell into backend container |
| `make flower` | Open Celery Flower UI |

---

## API Documentation

With the stack running, interactive API docs are available at:

- **Swagger UI**: [http://localhost/api/docs](http://localhost/api/docs)
- **ReDoc**: [http://localhost/api/redoc](http://localhost/api/redoc)
- **OpenAPI JSON**: [http://localhost/api/openapi.json](http://localhost/api/openapi.json)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.115, Python 3.11 |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic |
| Task queue | Celery 5 + Redis |
| Auth | JWT (python-jose) + bcrypt |
| Encryption | Fernet (AES-256-CBC) via cryptography |
| Frontend | React 18, TypeScript, Vite |
| UI | Tailwind CSS, Radix UI, shadcn/ui |
| Canvas | React Flow |
| State | Zustand |
| Proxy | Nginx |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Containers | Docker + Docker Compose |

---

## License

MIT License — see [LICENSE](./LICENSE).

Built with care by [notimefortears](https://github.com/notimefortears).
