# Planning Shard System

## Concept
The "Planning Shard" system is a forward-compatibility mechanism. When developing a current feature (e.g., Feature A), we often know it will eventually need to interface with a future feature on the roadmap (e.g., Feature G - WebUI). 

Instead of building Feature G now or forgetting the integration requirement later, we leave a "Shard"—a structured markdown file that records the architectural contract, API hooks, or design considerations required for that future integration.

When the development cycle reaches the milestone for Feature G, developers (and AI agents) must "collect the shards" related to Feature G to ensure no prior integrations are missed.

## Structure of a Shard
Shards are stored in `.cursor/plans/shards/` and MUST be tagged with an **Expected Version** and a **Targeted Feature**.

## Usage in the Agile Cycle
During the **Plan** and **Build** phases of the Agile loop, check the **`SHARD_LEDGER.md`** for shards matching your current **Version** OR **Feature**. During the **Document** and **Polish** phases, generate new shards for any future systems your current work impacts, tagging them clearly for the next developer.

## The Shard Ledger
To solve the visibility problem of "knowing if a shard exists," this directory contains a **`SHARD_LEDGER.md`**.
- It uses a tabular format to track **Shard Link**, **Targeted Feature**, **Expected Version**, and **Origin**.
- When you create a shard, you MUST add it to the table.
- This allows an agent or developer starting a new version or feature to instantly see every historical contract they must fulfill.