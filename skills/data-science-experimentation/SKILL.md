---
name: data-science-experimentation
description: 'Run structured LLM extraction experiments with baselines, cohort splits, error analysis, and cost-aware model routing recommendations.'
scope: ai-accounting-copilot
version: 2026-06-04
---

# Skill: Data Science Experimentation

## When to Use This Skill
- User asks to improve extraction accuracy.
- User asks for model comparison or regression analysis.
- User asks for confidence-threshold tuning.

## Prerequisites
- Evaluation dataset with known expected outputs.
- At least one baseline run with saved metrics.

## Step-by-Step Workflows
1. Define KPI target and experiment hypothesis.
2. Select cohort split and freeze test set.
3. Run baseline and candidate configurations.
4. Compute per-field and per-doc-type metrics.
5. Perform error clustering and root-cause analysis.
6. Produce recommendation with cost and latency impact.

## Gotchas
- Do not compare runs on different test sets.
- Do not report only aggregate accuracy; include field-level metrics.
- Always include confidence distribution and fallback rate.

## Output Checklist
- [ ] Baseline vs candidate comparison table
- [ ] Error taxonomy with counts
- [ ] Cost/latency impact
- [ ] Final recommendation and rollout guardrail
