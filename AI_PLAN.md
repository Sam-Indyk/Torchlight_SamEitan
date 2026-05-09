# AI incorporation plan — Torchlight Biosovereignty Hackathon, $100 prize track

This is a planning document. **Nothing in here is implemented yet.** It
exists so we can pick the right thing to build before we build it, and
so judges can see we thought through the trade-offs rather than dropping
a chatbot in for the bonus.

## The constraint to design around

Track 2 is a research deliverable with strong honesty requirements
(see [README.md](README.md#honesty-clauses) — null-result clause, no causal
language, no clinical recommendations). The wrong way to use AI here is
to attach a generative chatbot that confidently invents biological
claims about the crew. The judges will catch that immediately.

The right way is **AI grounded in the structured outputs we've already
computed**. The risk-profile JSON at
[`data/dashboard_data.json`](data/dashboard_data.json) is a finite,
well-defined object. An LLM reading from it cannot hallucinate a number
that isn't in there if we constrain its prompt correctly.

That framing rules out option D below and points at options A + B, with
C as a stretch goal.

## Options considered

### A. Per-astronaut AI narrative reports — *primary recommendation*

A new tab `AI Narrative` in [guiv2/](guiv2/) that, for each crew member,
sends the JSON slice for that astronaut to an LLM and renders a
2-paragraph factual narrative covering: which axes deviated most at R+1,
which recovered fastest, which still showed elevation at R+82, and one
honest caveat. The LLM does not see the raw OSDR data — it sees only
our precomputed numbers and is instructed to say only what those numbers
support.

**Why it's the right primary**

- Plug-and-play with the schema we already have. No analysis change.
- Differentiates from the deterministic [report_card.py](guiv2/components/report_card.py)
  view: that one is rule-based, terse, and identical structure across
  astronauts. The AI version is freer-form prose that can stitch
  observations together ("C003's inflammation is *suppressed*, not elevated,
  which is unusual for this cohort and worth a clinician's eye…").
- Cost: cents per generation; cache responses to disk so the 4 narratives
  generate once per JSON change.
- Free APIs that work: Anthropic free tier (Claude Haiku 4.5),
  OpenAI free credits (gpt-4o-mini), Groq free tier (Llama 3.3 70B).
  Anthropic is the natural fit since this whole project is built with
  Claude.

**The hard part — prompt design**

We give the model:

1. The astronaut's full JSON slice (axes, trajectories, recovery, multi-system).
2. A "what the numbers mean" rubric we author by hand (e.g., "scores
   are own-baseline z; positive = elevated; |z| < 0.3 is near baseline;
   half-life < 30 days is fast recovery").
3. Hard rules in the system prompt:
   - Quote every number you cite.
   - Distinguish own-baseline from population-anchored numbers.
   - If `is_mock` or `is_cohort_level`, label that observation as
     preliminary.
   - Use no causal language. No "spaceflight caused X."
   - End with a one-sentence honest caveat.

A simple validation step after generation: regex-scan the narrative for
any numeric claim, verify each number appears in the JSON slice. If a
number is invented, retry once, then fall back to the deterministic
report card with a "AI narrative unavailable" note. We don't ship
unverified numbers.

**Stretch:** generate a "longer-mission readiness brief" per astronaut
that recommends which markers a future mission should monitor — pulled
from each axis's `actionable_line` already in the JSON.

### B. Ask the dashboard — natural-language Q&A

A chat box at the top of the Mission Overview tab. Users type
"Who recovered fastest from inflammation?" or "Which body site shows
the strongest microbiome shift?" The LLM sees the JSON + a small
description of the schema, and answers in 1-3 sentences with the
relevant numbers cited.

**Why this is good**

- Highly visible. Judges will try it and see it work.
- Shows we understand grounded LLM use — the model is a *query
  translator*, not a content generator.
- Same JSON the rest of the dashboard reads, so answers are always
  consistent with the charts.

**Why it's risky**

- People will try to break it. "What does this mean for human
  spaceflight?" is the kind of question that pulls the model toward
  generic platitudes. Need a tight system prompt that refuses
  out-of-scope questions ("I can answer questions about the four
  Inspiration-4 crew at the ten observed timepoints. For broader
  inference, see the published priors panel.").
- Latency. Streamlit + LLM call = ~2-5s round trip. Acceptable but
  needs a spinner.

**Cost / API:** same as A. Cache identical question + JSON-hash pairs
to keep judges' repeated questions free.

### C. Local literature retrieval (RAG) — *stretch goal*

Embed Tierney 2024 + Park 2024 supplementary tables (and the 2-3 most
relevant cited papers) into a small in-process vector store. When the
prior-cohort overlay is shown, the LLM can pull the actual published
numbers from the embeddings instead of using the approximations we
hardcoded in [`published_priors.py`](risk_profile_claude/published_priors.py).

**Why it's a stretch**

- Real lift: getting clean text out of the supplementary PDFs/Excels.
- High value: replaces approximations with real published numbers,
  flips `is_approximate=False` in the JSON, makes the prior-cohort
  overlay rigorous.
- Tooling: `chromadb` or `lancedb` + `sentence-transformers` (free, local).
  No external API call needed for the embedding step.

If we have time after A and B work, C is the highest-value addition.

### D. Local model trained on the data — *not recommended*

E.g., autoencoder on the multi-omics features, flag astronauts whose
latent representation deviates most. Or anomaly detector. Or
trajectory predictor.

**Why we shouldn't**

- n = 4. Anything we train will overfit. That's not "demonstrating
  ML skill," it's modeling noise.
- Adds compute / dependency burden (PyTorch, GPU prep).
- Doesn't solve a real problem the dashboard has — the deterministic
  scoring already extracts all the signal from this dataset that's
  defensibly extractable.
- Would expose us to the same honesty issues as a hallucinating
  chatbot, in a different form.

If we wanted to use a local model honestly, the right one is:
**a clustering or PCA on the preflight pool** to flag whether one
astronaut sits at the edge of the preflight distribution — but
[`risk_profile_claude/build_risk_profile.py`](risk_profile_claude/build_risk_profile.py)'s
multi-system Mahalanobis already answers that question more cleanly,
without the ML overhead.

## Recommended build order

If we have **2 hours**, ship A only.

If we have **4 hours**, ship A + B with shared LLM client and shared
JSON-fetching helper.

If we have **6+ hours**, ship A + B + C, where C replaces the
approximate priors with verbatim ones from the embedded supplementary
tables.

## File layout when this lands

```
guiv2/
├── ai/
│   ├── __init__.py
│   ├── client.py              # thin LLM wrapper (Anthropic / Groq / fallback)
│   ├── prompts.py             # system prompts + the rubric for narratives + Q&A
│   ├── narrative.py           # per-astronaut narrative generator (option A)
│   ├── qa.py                  # natural-language Q&A (option B)
│   ├── retrieval.py           # local RAG over supp tables (option C, stretch)
│   ├── verify.py              # regex-check numeric claims against JSON
│   └── cache/
│       └── narrative_<crew>_<json_hash>.md   # disk-cached generations
├── components/
│   ├── ai_narrative_panel.py  # renders the 4 narratives in tabs
│   └── ai_qa_box.py           # input box + answer display
└── manifest.json (extends)
```

## API key handling

- Read from `ANTHROPIC_API_KEY` env var first. If missing, look in
  `.streamlit/secrets.toml` (Streamlit Community Cloud convention).
- If neither, render the AI tabs with a "Bring your own API key" textbox
  the user can paste into. Stored only in session state, never written
  to disk.
- `.gitignore` already covers `.streamlit/secrets.toml`. Double-check.

## Honesty surface area

The AI tab carries the same honesty banner as the rest of the dashboard,
plus an additional line:

> AI-generated text on this page is grounded in
> `data/dashboard_data.json` and verified to cite only numbers present
> there. Generation is non-deterministic; the same JSON may produce
> slightly different wording across runs. The deterministic versions of
> these summaries (rule-based) are still available in the *Per-astronaut
> report cards* panel.

## What we tell judges in the README pitch

> AI is used in two grounded roles: (1) generating per-astronaut
> narrative summaries from the structured risk-profile JSON, with a
> verification step that rejects any numeric claim not present in the
> source data; (2) translating natural-language questions ("who
> recovered fastest from inflammation?") into JSON queries that surface
> the right number. The AI never sees raw OSDR data and is constrained
> to talk only about what we have already computed.

That sentence is the pitch for the $100 prize. It's defensible because
it's true, it's specific, and it solves a real problem (translating
multi-omics output into astronaut-readable language) rather than adding
chatbot decoration.
