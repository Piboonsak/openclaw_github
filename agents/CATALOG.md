# Agents Catalog

This catalog is the source index for all agent definition files in this repository.

## Important Runtime Note

- Agent definitions are stored in `agents/` as version-controlled source.
- `.agent/` is reserved for runtime state/evidence in this repository and is not the source-of-truth folder for definitions.
- If an external runtime requires `.agent/`, use this catalog to resolve the source files and sync them at runtime.

## Agent Index

| Agent | File | Primary Focus | Default Model |
| --- | --- | --- | --- |
| Project Orchestrator | `agents/project-orchestrator.agent.md` | Timeline, dependencies, orchestration | GPT-5.3-Codex |
| Backend Extraction | `agents/backend-extraction.agent.md` | OCR/LLM extraction pipeline | GPT-5.3-Codex |
| Frontend UX | `agents/frontend-ux.agent.md` | UI workflow and review UX | GPT-5.3-Codex |
| DevOps Release | `agents/devops-release.agent.md` | Release, rollout, rollback safety | Claude Sonnet 4.6 |
| GitHub Project Ops | `agents/github-project-ops.agent.md` | Issue/project automation and hygiene | GPT-5 mini |
| QA Risk | `agents/qa-risk.agent.md` | Test gates and risk controls | GPT-5 mini |
| Data Science | `agents/data-science.agent.md` | Experiments, accuracy, drift analysis | GPT-5.3-Codex |
| DBA | `agents/dba.agent.md` | Schema/index/query guardrails | Claude Sonnet 4.6 |

## Quick Validation

Run:

```bash
npm run validate:agents-skills
```

