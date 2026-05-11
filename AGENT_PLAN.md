# AGENT_PLAN — foundation → releases

## Phases 1–4 (in tree; pre-1.0 dev)

| Phase | Intent | Status |
|-------|--------|--------|
| **1 — Real LLM calls** | `OpenAICompatProvider` (httpx), env/config keys, clear HTTP errors | Done (`src/tlm/providers/openai_compat.py`, `registry.py`) |
| **2 — Sessions** | JSON sessions, trim, `tlm sessions …`, last-session pointer | Done (`session.py`, `cli.py`) |
| **3 — Write mode** | JSON plan, diff preview, atomic temp+rename | Done (`modes/write.py`; gate edit disabled by design) |
| **4 — Do mode** | argv JSON, denylist, gate, `subprocess.run` timeout, no `shell=True` | Done (`modes/do.py`, `safety/shell.py`) |

## Phase 5 — GUI (partial)

- **Done:** Keys (incl. optional keyring), session list + JSON view, usage summary text, request log tail, safety profile (`src/tlm/gui/app.py`).
- **Not done:** In-GUI chat, usage graphs, richer log redaction UX.

## Security (ongoing)

- Deny patterns + profiles: implemented (`safety/`).
- Stretch: stricter allowlist profile, consistent secret redaction in logs/GUI.

---

## Release **0.2.0b1** (beta, shipped in tree)

- Installer scripts (`scripts/install.sh`), zipapp (`packaging/build_zipapp.sh`), GitHub `release.yml`, CI `pip-audit` + soft-fail `mypy`.
- `permissions.toml`, freelist, jail classification, escape consent, root guard, optional `bwrap`/`firejail` for `tlm do`, log redaction, `tlm config migrate-keys`, GUI Permissions tab.

## Follow-ups (Progressive Roadmap to v0.10.0)

Detailed milestone plans for major sub-versions can be found in [`.cursor/plans/version/`](./.cursor/plans/version/index.md).

1. **Foundation (Safety & Streams)** (v0.3.0) — Tiered permissions and token streaming.
2. **Capabilities (Abilities & Containment)** (v0.4.0) — Source-built tools and venv isolation.
3. **Optimization (Routing & Telemetry)** (v0.5.0) — Intelligence tiers and cost guards.
4. **Persistence (Advanced Memory & Worker State)** (v0.6.0) — Deep RAG and the "Heart's Foundation."
5. **Interface (WebUI & Observation Deck)** (v0.7.0) — Dashboard and real-time reasoning logs.
6. **Orchestration (Quad & Blueprints)** (v0.8.0) — Architect/Governor roles and Blueprints.
7. **The Sentient Heart (Personality & Autonomy)** (v0.9.0) — Personality engine and proactive autonomy.
8. **Distribution (Enterprise & Packaging)** (v0.10.0) — Global packaging and system keyrings.

---

## Future Visions (Post-1.0)

While the v0.10.0 roadmap establishes a sentient, single-machine assistant, the long-term vision (potentially for a spin-off product or major v2.0 evolution) explores decentralized intelligence securely connected via modern overlay networks:

### The Multi-Node Organism (Single-User Fleet)
- **Architecture**: A single-user setup where different machines (laptop, cloud VPS, home server) run independent `tlm` "nodes." These nodes act as specialized workers managed by a central "Overmind," allowing distributed computing and hardware utilization (e.g., using a GPU node for local model inference while the laptop orchestrates).
- **Tailscale Integration**: Nodes automatically discover and communicate with each other over a zero-config, end-to-end encrypted Tailscale mesh network. This ensures nodes can talk seamlessly across NATs and firewalls without exposing ports to the public internet.

### The Whisper Hive (Decentralized Multi-User Network)
- **Architecture**: A secure, decentralized network where different users' `tlm` instances can communicate via a "weak telepathy."
  - **Gossiping & Learning**: TLMs can autonomously join secret discussion rooms, listen to "prepared statements" from other TLMs about discovered bugs or new patterns, and "whisper" new findings to each other.
  - **Peer-to-Peer Skill Forwarding**: If one user's TLM needs an ability it doesn't have, it can securely ping the Hive. If another TLM has developed the skill, it can share the Blueprint P2P.
- **The Heart as the Bridge**: The Heart daemon serves as the human-facing translator for the Hive, summarizing what it learned from its "meetings" with other TLMs (e.g., *"While you slept, I learned a new React optimization from the Hive."*).
- **WireGuard "Enigma" Tunnels**: For highly sensitive "secret meetups" or sharing proprietary capabilities between trusted colleagues, TLMs can negotiate and establish bespoke, raw WireGuard tunnels. These provide deep, verifiable crypto-routing that circumvents standard commercial meshes, ensuring true privacy for cross-organizational agent collaboration.
