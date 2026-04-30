# Job-search v1 — backlog & future options

This doc tracks deferred-but-considered work for the personal job-search assistant
that lives on the `feat/job-search-v1` branch.

## Currently shipped (deterministic similarity)

`/jd-match` parses a pasted JD via [analysis/jd_parse.py](../analysis/jd_parse.py)
and ranks active jobs by hand-tuned features:

- Skill overlap (Jaccard against `must_have_skills` + `stack_signals`)
- `role_family` match
- `seniority` within ±1 level
- Sector match
- Job freshness bonus

Pipeline: [analysis/job_search.py](../analysis/job_search.py) → reuses
`shortlist_jobs` and `_score_job` from [analysis/resume_fit.py](../analysis/resume_fit.py)
by constructing a pseudo-profile from the parsed JD.

Trade-offs of the current approach:

- ✅ Cheap (one Groq call to parse, no LLM per-job)
- ✅ Explainable — every match shows which skills overlapped
- ✅ Reuses tested infrastructure
- ❌ Misses semantically-similar jobs whose surface tokens don't overlap
  (e.g., "Distributed Systems Engineer" ≈ "Backend Platform Engineer" but
   shares zero skill tokens if the JDs phrase things differently)
- ❌ Ranking saturates around skill-list quality — if a JD uses uncommon
  vocabulary, the scorer underweights it

## Future option: embedding-based semantic search

When the deterministic scorer hits quality ceiling, the next move is vector
similarity over JD embeddings. Sketch:

### Data layer

- Add `pgvector` extension (or stay on SQLite + a flat `BLOB` column for v1)
- New column: `job_postings.description_embedding VECTOR(1024)`
  - Could also live in a side table `job_embeddings(job_id, embedding, model_version)`
    if we want multiple embedding models alongside
- Embed every active job at scrape-time + on-demand for any stale rows
- Re-embed when description changes (track via hash)

### Embedding model choice

| Option | Cost | Dim | Notes |
|---|---|---|---|
| OpenAI `text-embedding-3-small` | $0.02/1M tokens | 1536 | cheap, good baseline |
| OpenAI `text-embedding-3-large` | $0.13/1M tokens | 3072 | better, expensive at scale |
| Voyage AI `voyage-3` | $0.18/1M tokens | 1024 | strongest open benchmarks |
| Local (e.g., `nomic-embed-text` via ollama) | infra-only | 768 | no per-call cost, slower |

For a single-user prototype: `text-embedding-3-small` is the right call. ~10K
active jobs × ~500 tokens each ≈ 5M tokens × $0.02/M = **~$0.10 to embed the
whole DB**, refresh quarterly = ~$0.40/yr.

### Query path

```python
def find_similar_jobs_semantic(jd_text: str, *, limit: int = 20) -> list[dict]:
    parsed = parse_jd(jd_text)             # for displayable parsed fields
    query_emb = embed(jd_text)             # single embedding call
    # SQL: ORDER BY embedding <=> :query_emb LIMIT N
    return queries.nearest_jobs(query_emb, limit)
```

### Hybrid scoring (the actual best v2)

Don't replace the deterministic scorer — *combine* it with semantic similarity:

- `final_score = 0.4 * deterministic + 0.6 * semantic_cosine_similarity`
- Surface both sub-scores in the UI so the user can see *why* something ranked

Hybrid is the standard play in real-world recommenders because it captures
both interpretable feature matches AND semantic nuance. Pure-vector can
return embarrassing misses (Amazon's "junior engineer with Pytest" → "VP Eng
who once wrote a Pytest hello world" because their about-me embedding
clustered around testing words).

### Cost ceiling check

At ~1 search per click and the cheap model: each query is ~1 embed call ≈ 500
tokens × $0.02/M ≈ **$0.00001 per click**. Embedding the index dominates
total spend by ~5 orders of magnitude. Negligible.

### When to actually do this

Defer until: (a) you've used `/jd-match` for a few weeks and have specific
"this should have ranked higher" complaints, (b) the deterministic scorer's
tail is clearly the bottleneck (vs. JD-parse quality, which is upstream), and
(c) you're willing to add OpenAI as a second LLM dependency alongside Groq.

## Other deferred items

- **Per-person manual reveal button** in the outreach panel. Endpoint exists
  (`POST /api/outreach/people/{person_id}/enrich`) but no UI button. Currently
  we auto-enrich top 1 per archetype; user-driven reveal would let you only
  spend credits on people you'd actually message.
- **Outreach-send tracking**: a "mark sent" button + outreach status field
  (sent / replied / interview / passed) so the user can track funnel and
  retroactively learn which prompt patterns work. Pure UI work; schema column
  already lives on `outreach_drafts.user_edits`.
- **Free-text query → jobs** (the deferred "Feature 1" from the original
  request). LLM parses "Senior PM at consumer fintechs" into structured
  filters that hit `/api/jobs`. Smaller lift than JD-match because it reuses
  the existing job filter UI.
- **Asker-side data** (LinkedIn CSV, Gmail OAuth, calendar) for warm-intro
  paths. Defers the warm-intro layer entirely; biggest single quality lift.
