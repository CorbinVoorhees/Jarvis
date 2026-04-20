# Environment Configuration

Jarvis loads configuration from system environment variables.

Configuration is defined in `app/config.py`.

This project does not require a `.env` file. Environment values should be provided through the operating system environment.

---

## Current Variables

### APP_NAME
- Purpose: display name of the application
- Default: `Jarvis`

### APP_ENV
- Purpose: current runtime environment
- Default: `development`

### LOG_LEVEL
- Purpose: application logging level
- Default: `INFO`

---

## PowerShell Setup

Set values for the current session:

```powershell
$env:APP_NAME="Jarvis"
$env:APP_ENV="development"
$env:LOG_LEVEL="INFO"