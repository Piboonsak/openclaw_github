---
name: create-skill
scope: ai-accounting-copilot
version: 2026-06-04
---

# /create-skill

Create one new skill from conversation context and repository goals.

## Required behavior
1. Read current conversation summary and existing skills.
2. Prevent overlap by checking if similar skill exists.
3. Generate a new skill with practical, repeatable steps.
4. Include verification checklist and expected outputs.

## Example target
- prepare-github-project: bootstrap repo plan, create epics/tasks, create full-detail issues, link to GitHub Project, sync labels/fields, and deduplicate draft cards.
