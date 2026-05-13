# Shard: Role-Based Model Selection

## Status
- **Phase**: Post-Foundation
- **Status**: Draft / Future Requirement

## Context
Currently, `tlm` uses a single active provider and model (global default or per-provider override). 
In the future, we want to support **Roles** (e.g., `ask`, `write`, `do`, `summary`, `web-search`) where each role can have its own preferred model or a list of models with fallbacks and limits.

## Requirements
1. **Multiple Models per Role**: A role can be assigned a list of (provider, model) pairs.
2. **Fallbacks**: If the primary model for a role fails (e.g., rate limited), `tlm` should attempt the next one in the list.
3. **Limits**:
    - **Request Limits**: Maximum number of requests per session or time window for a specific role/model.
    - **Token Limits**: Budget tokens for expensive models (e.g., restrict GPT-4o for `summary` but allow for `write`).
4. **Configuration Schema**:
    ```toml
    [roles.write]
    models = [
        { provider = "openai", model = "gpt-4o", max_tokens = 50000 },
        { provider = "deepseek", model = "deepseek-v4-flash" }
    ]
    request_limit = 50

    [roles.ask]
    models = [{ provider = "openrouter", model = "auto" }]
    ```

## Implementation Notes
- This will require a major refactor of `get_provider` and `UserSettings`.
- Safety gates (`tlm/safety/`) should be aware of role-based limits.
- UI will need a "Roles" tab to manage these associations.
