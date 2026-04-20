# Services

This directory contains business logic for Jarvis features.

Services should:
- implement feature behavior
- be reusable by API routes, workers, and agents
- avoid depending directly on HTTP request objects

Services should not:
- contain route definitions
- contain vendor-specific API wrappers
- become a dumping ground for unrelated helpers