---
name: cost-timeline-optimizer
description: 'Optimize execution plan and model spend with dependency-aware scheduling and risk-adjusted prioritization.'
scope: ai-accounting-copilot
version: 2026-06-04
---

# Skill: Cost Timeline Optimizer

## Purpose
Optimize delivery schedule and AI token spend across multi-epic implementation.

## When to Use This Skill
- Planning 2-week execution for multiple epics
- Re-prioritizing backlog under budget/time pressure
- Choosing model tier for each task

## Step-by-Step Workflows
1. Read issue labels: epic, phase, priority.
2. Build dependency graph and identify critical path.
3. Route models by task complexity:
   - critical architecture or RCA -> full model
   - medium formatting or documentation -> mini model
4. Apply WIP limits and avoid parallel overload.
5. Output day-by-day execution plan and risk controls.

## Output Checklist
- Sprint day plan
- Critical path list
- Cost forecast by model tier
- Risk and fallback actions
