# AI usage disclosure

For judges: a clear and complete account of where AI was used in this
project, where it wasn't, and how we kept it honest. The
[README's AI usage clause](README.md#honesty-clauses) is the short
version; this file is the long one.

This project has two kinds of AI usage that should be evaluated separately:

1. **Runtime AI features** — AI features that live inside the dashboard
   itself, that judges and end users interact with.
2. **Development-time AI use** — AI tools we used while building the
   project (writing code, drafting prose, debugging).

The first is what we'd like the **$100 AI-incorporation prize** to be
evaluated on. The second is disclosed for transparency.

## 1. Runtime AI features (in the dashboard)

Two features under the **AI · grounded in the data** tab in
[guiv2/](guiv2/):

### 1a. Per-astronaut narrative summaries
[`guiv2/components/ai_narrative_panel.py`](guiv2/components/ai_narrative_panel.py)
+ [`guiv2/ai/narrative.py`](guiv2/ai/narrative.py)

For each crew member, Claude reads a small JSON slice of the
precomputed risk profile and writes a 2-paragraph factual summary
covering: largest R+1 deviation, recovery profile, within-cohort
context, one suppressed-axis observation if any, and a one-sentence
honest caveat.

### 1b. Natural-language Q&A on the dashboard
[`guiv2/components/ai_qa_box.py`](guiv2/components/ai_qa_box.py)
+ [`guiv2/ai/qa.py`](guiv2/ai/qa.py)

A chat-style input box. Users ask questions like "who recovered fastest
from inflammation?" and Claude reads the dashboard JSON and answers in
1–3 sentences, citing numbers verbatim from the source.

### How both features are kept honest

- **The model never sees raw OSDR data.** It only sees
  [`data/dashboard_data.json`](data/dashboard_data.json), the structured
  output of our deterministic scoring pipeline. Every number it can
  cite is one we precomputed.
- **System prompts** ([`guiv2/ai/prompts.py`](guiv2/ai/prompts.py))
  are explicit:
  - "Never invent a number. Every numeric claim must appear verbatim
    in the JSON the user gives you."
  - "Never use causal language."
  - "If `is_mock=true` or `is_cohort_level=true`, label the observation
    as preliminary."
  - "Never make clinical recommendations."
  - "Redirect out-of-scope questions."
- **Numeric grounding verifier** ([`guiv2/ai/verify.py`](guiv2/ai/verify.py)):
  every AI output is regex-scanned for numbers, and each number is
  verified to appear in the source JSON (with rounding and percent ↔
  fraction tolerance). If anything is unverified:
  - Narratives: one-shot retry with a stricter reminder; if still
    unverified, the unverified numbers are surfaced to the user as a
    yellow warning above the narrative.
  - Q&A: unverified numbers are flagged inline. The answer renders
    anyway so users can judge for themselves, but the warning is
    explicit.
- **Verifier badge** is shown after every AI output:
  - Green ✓ "Every number is grounded in the dashboard JSON."
  - Yellow ⚠ "Unverified numbers: [...] — these don't appear in the
    JSON, treat with skepticism."
- **Caching** ([`guiv2/ai/cache/`](guiv2/ai/cache/)) — narrative outputs
  are cached on disk by `(crew_id, json_hash)` so reloading the page
  doesn't burn tokens or produce nondeterministic re-generations. The
  cache is gitignored.

### Models and APIs

- **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) via the Anthropic
  API. Picked for cost (free tier covers light hackathon use) and
  latency (~1–2 seconds per generation).
- API key handling: read from `ANTHROPIC_API_KEY` env var, then
  `.streamlit/secrets.toml`, then a session-only password textbox in
  the GUI. The key is **never written to disk** by our code, and
  `.streamlit/secrets.toml` is gitignored.
- Total tokens sent per dashboard load: ≤ ~5 KB per AI call (the
  trimmed JSON slice + system prompt). Free tier comfortably handles
  the four narratives + several Q&A queries per session.

### What does NOT depend on AI

A judge can disable both AI features (set no API key) and the rest of
the dashboard works unchanged. The risk profile, the trajectory
charts, the multi-system Mahalanobis, the recovery-rate fits, the
flow diagram, and the molecular-perturbation tables are all
deterministic — no AI in their compute path.

## 2. Development-time AI use

We used AI tooling to build this project and disclose that openly.

### What AI helped write

- **The bulk of the code** in [`risk_profile_claude/`](risk_profile_claude/)
  and [`guiv2/`](guiv2/) was scaffolded by Claude (Opus 4.7 via Claude
  Code, in the user's IDE) following human-authored design briefs. A
  human (the project owner) directed each step, reviewed the diffs,
  and accepted or revised them.
- **Prose** in this file, [`README.md`](README.md),
  [`risk_profile_claude/README.md`](risk_profile_claude/README.md),
  [`risk_profile_claude/SCHEMA.md`](risk_profile_claude/SCHEMA.md),
  [`AI_PLAN.md`](AI_PLAN.md), [`guiv2/README.md`](guiv2/README.md),
  and the methods notes inside the dashboard panels was AI-assisted.
  Every clinical-sounding claim was checked against the source data
  or the cited literature.
- **Commit messages** are AI-drafted from human-reviewed diffs.

### What AI did NOT do

- **No statistics were invented by AI.** Every score, z-value, half-
  life, Mahalanobis distance, and edge weight in the dashboard comes
  from a deterministic computation in
  [`risk_profile_claude/build_risk_profile.py`](risk_profile_claude/build_risk_profile.py)
  reading directly from the OSDR cache and the analysis-pipeline
  CSVs.
- **No synthetic astronauts.** The dataset contains four real crew
  members from Inspiration-4. We did not generate or simulate any
  additional data, and we explicitly flagged this as not-defensible
  in our early planning.
- **No AI-fabricated citations.** Every paper cited
  ([Tierney et al. 2024](risk_profile_claude/published_priors.py),
  [Park et al. 2024](risk_profile_claude/published_priors.py),
  Kleiner 2013, Biancotto 2013, Said 2021, NHANES) is a real
  publication. The numerical reference values we extracted from those
  papers and hardcoded in
  [`risk_profile_claude/population_reference.py`](risk_profile_claude/population_reference.py)
  and [`risk_profile_claude/published_priors.py`](risk_profile_claude/published_priors.py)
  are flagged as `is_approximate=True` so a downstream reader knows
  they're calibrated, not lifted verbatim.
- **No clinical recommendations.** This is a research artifact, not
  medical advice. No AI output recommends or implies a fly/no-fly
  decision for any astronaut.

### Models used during development

- **Claude Opus 4.7 (1M context)** via Claude Code for code generation,
  refactoring, debugging, and prose drafting.
- No other AI tools (no GitHub Copilot, no ChatGPT, no Gemini, no
  Cursor) were used in this project.

## 3. Data privacy

- The Inspiration-4 OSDR data is publicly released by NASA. No private
  health data leaves the local machine.
- Per-astronaut JSON slices sent to the Anthropic API are subject to
  Anthropic's standard API policies. The crew are pseudonymized by
  OSDR as C001-C004; we do not transmit real names.
- API keys are user-supplied and not logged or transmitted anywhere
  by our code.

## 4. The pitch in one sentence

AI is used in two grounded roles inside the dashboard: **per-astronaut
narrative summaries** generated from precomputed structured JSON, and
**natural-language Q&A** on the same JSON, both with a regex verifier
that flags any numeric claim not present in the source data. The model
never sees raw OSDR data and is constrained — by system prompt, by
verifier, and by visible badge — to talk only about what the
deterministic analysis pipeline already computed.

## 5. Where to look in the code

| What | File |
|---|---|
| Prompts (system + user templates) | [`guiv2/ai/prompts.py`](guiv2/ai/prompts.py) |
| LLM client wrapper | [`guiv2/ai/client.py`](guiv2/ai/client.py) |
| Per-astronaut narrative generator | [`guiv2/ai/narrative.py`](guiv2/ai/narrative.py) |
| Q&A handler | [`guiv2/ai/qa.py`](guiv2/ai/qa.py) |
| Numeric grounding verifier | [`guiv2/ai/verify.py`](guiv2/ai/verify.py) |
| Narrative panel UI | [`guiv2/components/ai_narrative_panel.py`](guiv2/components/ai_narrative_panel.py) |
| Q&A panel UI | [`guiv2/components/ai_qa_box.py`](guiv2/components/ai_qa_box.py) |
| Design rationale | [`AI_PLAN.md`](AI_PLAN.md) |
