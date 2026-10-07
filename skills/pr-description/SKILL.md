---
name: pr-description
description: Write concise pull request descriptions from task context and change evidence using the required four-section template. Use when the user asks to draft or refine a PR description.
---

# PR Description

Draft a concise, factual PR description from the task, relevant session history, conversation, and available change evidence (such as the diff, tests, build results).

## Output

Use this template, preserving the headings and order:

```markdown
## 1. What problem is this PR solving?

## 2. How does this PR solve the problem?

## 3. How was this change tested?

## 4. What products/areas are affected?
```

## Guidelines

- Keep each answer brief and specific; prefer one or two sentences.
- Explain the user or system problem, the substantive change, and the affected product or code areas.
- Report only tests or checks known to have run. If none are known, say so; do not imply validation occurred.
- Use relevant session history for task intent and decisions; use the diff and recorded command results to substantiate changes and tests. Do not treat a planned or discussed test as one that ran.
- Do not guess at behavior, impact, or test results.
- If key information cannot be established from context, state what is unknown briefly rather than making it up.
- Return only the completed template unless the user asks for explanation or another format.
