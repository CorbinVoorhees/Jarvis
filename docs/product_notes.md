# Product Notes

This file contains evolving product ideas, priorities, and notes for Jarvis.

It is intended to capture product direction without requiring every idea to become a formal specification immediately.

---

## Current Direction

Jarvis is intended to become a personal life and project management system with support for structured workflows and AI-assisted interactions.

The current backend foundation is being built first.

---

## Near-Term Priorities

- Establish clean backend architecture
- Keep the codebase organized for future AI-assisted development
- Add the first real feature only after the foundation is stable

---

## Product Themes

- Personal task and project management
- AI-assisted workflows
- Structured input and output
- Expandable architecture for future integrations
- Support for multiple input methods over time

---

## Future Ideas

- Text-based capture flow
- SMS-based input
- Voice interface
- Project-oriented planning workflows
- Scheduling support
- Reminder and review workflows

---

## Notes

- The system should remain modular as features are added
- New ideas do not need to be immediately implemented
- Formal feature specifications can be added later as separate documents when needed

---

## Capture Feature (v1)

### Goal

Transform raw text input into structured JSON

### Supported Types
- task
- note
- question

### Inputs
- Add cheese to my shopping list.
- Put on my calendar I have a dentist appointment Thursday at 2pm.
- What is the capital of Australia?
- Make a note that I should use loctite on this wheel hub.

### Outputs
{
  "type": "task",
  "title": "Add cheese to shopping list",
  "content": null,
  "question": null,
  "time": null,
  "raw": "Add cheese to my shopping list."
}

{
  "type": "task",
  "title": "Dentist appointment",
  "content": null,
  "question": null,
  "time": "Thursday at 2pm",
  "raw": "Put on my calendar I have a dentist appointment Thursday at 2pm."
}

{
  "type": "question",
  "title": null,
  "content": null,
  "question": "What is the capital of Australia?",
  "time": null,
  "raw": "What is the capital of Australia?"
}

{
  "type": "note",
  "title": null,
  "content": "Use loctite on wheel hub",
  "question": null,
  "time": null,
  "raw": "Make a note that I should use loctite on this wheel hub."
}

