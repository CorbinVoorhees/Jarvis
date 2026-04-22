# Jarvis

Jarvis is a personal life and project management system designed to support task tracking, planning, and AI-assisted workflows.

This repository contains the backend application built with FastAPI.

---

## Current Status

This project is in early development.

Implemented so far:
- FastAPI application setup
- Health endpoint (`/health`)
- Basic test infrastructure
- Configuration via system environment variables

---

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- Pytest
- Ruff (linting)
- Black (formatting)

---

## Project Structure

```
app/
  api/           # HTTP routes
  core/          # shared utilities (logging, exceptions, etc.)
  schemas/       # data validation models
  models/        # database/domain models
  services/      # business logic (future)
  agents/        # LLM/AI logic (future)
  integrations/  # external services (OpenAI, Twilio, etc.)
  workers/       # background jobs (future)
  config.py      # environment configuration
  main.py        # application entrypoint

tests/           # test suite
docs/            # architecture and design notes
```

---

## Getting Started

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Run the application

```powershell
make run
```

---

## API

### Base URL

```text
http://127.0.0.1:8000
```

### Health check

```text
GET /health
```

### Docs

```text
http://127.0.0.1:8000/docs
```

---

## Testing

```powershell
make test
```

---

## Formatting and Linting

```powershell
make lint
make format
```

---

## Development Guidelines

- Keep API routes thin
- Put logic in `app/services`
- Use schemas for validation
- Add tests for new functionality

---

## Future Plans

- Task and project management
- Text capture and parsing
- SMS integration
- Voice agent interface
