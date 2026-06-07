---
name: create-agents
scope: ai-accounting-copilot
version: 2026-06-04
---

# /create-agents

Create role-based agent definition files for current project tasks.

## Inputs
- Epic/task breakdown
- Timeline target
- Cost constraints

## Required Outputs
- agents/project-orchestrator.agent.md
- agents/backend-extraction.agent.md
- agents/frontend-ux.agent.md
- agents/devops-release.agent.md
- agents/github-project-ops.agent.md
- agents/qa-risk.agent.md

## Constraints
- Each agent must include mission, responsibilities, and quality gates.
- Include cost and timeline controls.
- Keep content actionable and specific to this repo.
