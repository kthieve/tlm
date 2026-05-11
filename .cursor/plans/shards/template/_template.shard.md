# Shard: [Brief Name]
**Targeted Feature:** [e.g., WebUI, Memory, Orchestrator]
**Expected Version:** [e.g., v0.7.0]
**Originating Feature:** [What you are building right now]
**Date:** [YYYY-MM-DD]

## Context
[Briefly explain why this shard was created. e.g., "We are building Subagents, but they will eventually need to be visualized in the WebUI."]

## Requirements / Contracts
[List the specific hooks, APIs, or architectural decisions made in the Originating Feature that the Target Feature MUST respect or utilize.]
- e.g., "The Subagent state is serialized to `.tlm/workers/[id].json`. The WebUI MUST read this file to generate the Live-Map."

## Warnings / Pitfalls
[List any potential issues or edge cases to watch out for when this shard is finally implemented.]
- e.g., "Do not lock the worker JSON file while the WebUI is reading it, or it will crash the background daemon."