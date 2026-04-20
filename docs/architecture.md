# Architecture

Jarvis is structured as a layered backend application.

The goal of this structure is to keep responsibilities separated clearly so the codebase can grow without becoming difficult to maintain.

---

## High-Level Structure

The application is organized into the following main layers:

- `app/api/` for HTTP routes and request handling
- `app/schemas/` for validation models and API contracts
- `app/services/` for business logic
- `app/agents/` for AI and LLM-related behavior
- `app/integrations/` for external service wrappers
- `app/models/` for domain and database-backed models
- `app/workers/` for background jobs and scheduled tasks
- `app/core/` for shared utilities and infrastructure concerns

---

## Layer Responsibilities

### API Layer

Location: `app/api/`

Responsibilities:
- define HTTP routes
- parse requests
- return responses
- call services

This layer should remain thin and should not contain complex business logic.

---

### Schema Layer

Location: `app/schemas/`

Responsibilities:
- define request and response models
- validate structured data
- provide shared contracts between layers

Schemas should be used whenever structured input or output needs validation.

---

### Service Layer

Location: `app/services/`

Responsibilities:
- implement business logic
- coordinate feature behavior
- serve as the main reusable application logic layer

Services should be callable from routes, workers, and agents.

---

### Agent Layer

Location: `app/agents/`

Responsibilities:
- contain AI and LLM-related logic
- manage prompt orchestration
- parse model outputs
- hold agent-specific workflows

This layer should stay separate from normal business logic so AI behavior can evolve independently.

---

### Integration Layer

Location: `app/integrations/`

Responsibilities:
- wrap external APIs and services
- isolate vendor-specific logic
- provide reusable interfaces for services and agents

Examples of future integrations include OpenAI, Twilio, GitHub, and calendar systems.

---

### Model Layer

Location: `app/models/`

Responsibilities:
- define internal domain objects
- define database-backed models when a database is introduced

---

### Worker Layer

Location: `app/workers/`

Responsibilities:
- run background jobs
- process asynchronous tasks
- support scheduled operations

---

### Core Layer

Location: `app/core/`

Responsibilities:
- shared utilities
- logging
- exceptions
- other cross-cutting infrastructure concerns

This layer should not become a dumping ground for unrelated feature logic.

---

## Request Flow

The normal request flow should follow this pattern:

1. Request enters through `app/api/routes/`
2. Route validates input and calls a service
3. Service executes business logic
4. Service may call integrations or agents when needed
5. Response is validated and returned to the client

In general, feature code should flow downward through these layers rather than bypassing them.

---

## Configuration

Application configuration is managed through `app/config.py`.

Configuration values are loaded from system environment variables.

New configuration should:
- be added to `app/config.py`
- be documented in `docs/environment.md`

---

## Testing Strategy

Tests are organized by layer:

- `tests/api/` for route and endpoint behavior
- `tests/services/` for business logic
- `tests/agents/` for AI-related logic
- `tests/integrations/` for external service wrappers

New features should include tests at the appropriate layer.

---

## Design Principles

- Keep route handlers thin
- Keep business logic out of `main.py`
- Use schemas for structured validation
- Isolate external service wrappers
- Keep AI logic separate from core application logic
- Prefer clear structure over clever abstractions
- Prefer small, focused changes over large rewrites

---

## Future Growth

This structure is intended to support gradual expansion into features such as:
- task and project management
- text capture pipelines
- SMS input
- voice interfaces
- scheduling and planning workflows
- AI-assisted prioritization and review