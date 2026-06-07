---
name: prepare-github-project
description: 'Bootstrap a new GitHub project end-to-end: repo folder plan, epics/tasks docs, full-detail issues, label strategy, project linkage, field sync, and draft deduplication.'
scope: ai-accounting-copilot
version: 2026-06-04
---

# Skill: Prepare GitHub Project

## When to Use This Skill
- User asks to set up a new project board with epics and tasks.
- User needs issue creation with complete acceptance criteria.
- User asks to sync issue labels into project fields like Phase and Priority.

## Inputs
- Project name
- Epic list and task list
- Timeline target (default 2 weeks)
- Priority rules and phase mapping

## Step-by-Step Workflows
1. Create docs structure:
   - docs/PoC/plan/README.md
   - docs/PoC/plan/epic-*/EPIC-*-TASKS-DETAIL.md
   - docs/PoC/plan/MASTER-ROADMAP.md
2. Create labels in repo:
   - type:task
   - priority:critical/high/medium
   - phase:1/2/4 (or provided phases)
   - epic:1..N
3. Create issues from tasks with full details:
   - Purpose
   - Acceptance criteria
   - Workflow
   - Dependencies
   - CI/CD checklist
4. Add issues to GitHub Project.
5. Ensure project fields include Phase and Priority.
6. Sync issue labels to project fields.
7. Remove duplicate draft cards.
8. Verify final counts: open task issues equals project task items.

## Gotchas
- Never leave reference-only placeholders in issue body when user asked for full details.
- Always deduplicate by canonical key `TASK-###` before creating new issue.
- Project may already contain legacy draft cards; remove only duplicate task drafts.

## Output Checklist
- [ ] Repo folder structure ready
- [ ] Epic docs created
- [ ] Issues created with full bodies
- [ ] Labels applied
- [ ] Project linked and deduplicated
- [ ] Phase/Priority fields set
