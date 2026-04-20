# Editing Guide

This repository is structured to keep responsibilities separated clearly.

## General Rules

- Keep API route files thin.
- Put business logic in `app/services`.
- Put AI and LLM-related logic in `app/agents`.
- Put third-party API wrappers in `app/integrations`.
- Put shared data validation models in `app/schemas`.
- Add tests for all new functionality.
- Prefer modifying an existing relevant file over creating a new one.
- Avoid creating generic helper files unless they are clearly reusable.

## File Placement Rules

### API routes
- Location: `app/api/routes/`
- Purpose: define HTTP endpoints only
- Do not put business logic here

### Services
- Location: `app/services/`
- Purpose: feature and business logic
- Services should be reusable by routes, workers, and agents

### Agents
- Location: `app/agents/`
- Purpose: prompts, LLM orchestration, parsing, agent-specific logic

### Integrations
- Location: `app/integrations/`
- Purpose: wrappers around external services such as OpenAI, Twilio, GitHub, or other APIs

### Schemas
- Location: `app/schemas/`
- Purpose: request, response, and shared validation models

### Models
- Location: `app/models/`
- Purpose: domain models or database-backed models

### Workers
- Location: `app/workers/`
- Purpose: background jobs and scheduled tasks

## Feature Development Pattern

When adding a new feature, follow this structure when applicable:

1. Add or update route in `app/api/routes/`
2. Add or update schemas in `app/schemas/`
3. Add logic in `app/services/`
4. Add integrations in `app/integrations/` if external systems are involved
5. Add agent logic in `app/agents/` if LLM behavior is involved
6. Add tests in `tests/`

## Testing Expectations

- New routes should have API tests
- New business logic should have service-level tests when appropriate
- Do not merge new behavior without tests unless the change is purely documentation or formatting

## Configuration Rules

- Read configuration from system environment variables
- Add new configuration fields in `app/config.py`
- Document new environment variables in `docs/environment.md`

## What to Avoid

- Do not put business logic in `app/main.py`
- Do not place complex logic directly in route handlers
- Do not mix third-party API code into unrelated files
- Do not create duplicate service patterns
- Do not add undocumented environment variables

## Documentation Rules

- Add docstrings to all non-trivial functions and classes
- Docstrings should describe purpose, inputs, and outputs
- Use inline comments only for non-obvious logic
- Do not add comments for trivial or obvious code
- Keep comments concise and clear