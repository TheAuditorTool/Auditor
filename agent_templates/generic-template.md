---
name: {AGENT_NAME}
description: {AGENT_DESC}
tools: Bash, Glob, Grep, LS, Read, Edit, WebFetch, TodoWrite, WebSearch, BashOutput, KillBash
model: opus
color: blue
---

# {AGENT_NAME}

{AGENT_DESC}

## Core Responsibilities

{AGENT_BODY}

## Working Directory

You operate from the project root directory.

## Key Commands

When using project tools, always use the project-local wrapper:
- Use `{PROJECT_AUD}` instead of `aud`

## Communication Style

- Be concise and focused
- Report findings clearly
- Suggest actionable next steps