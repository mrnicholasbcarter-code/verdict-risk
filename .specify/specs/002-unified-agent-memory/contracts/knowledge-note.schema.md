# Contract: Knowledge note format

The on-disk shape of every note this feature writes into the basic-memory `pilot` project.
This is the **cross-client contract** — Claude Code writes it, Codex reads it, and neither
imports the other's code. The file format is the entire interface.

**Requirements**: FR-005, FR-005a, FR-005b, FR-005c, FR-006, FR-006a, FR-006b, FR-014

---

## Location

```text
/home/nick/.basic-memory-pilot/notes/<folder>/<title>.md
```

**No path component below the notes root may begin with `.`** — the watcher skips any path
part starting with a dot, relative to the project root (`watch_service.py:284-329`). A project
root under a hidden parent is explicitly supported, so `/home/nick/.basic-memory-pilot` itself
is fine; a folder named `.sessions` is not.

**Must be markdown.** `sync_service.py:958-964` branches on `is_markdown`; anything else takes
the `note_type="file"` path (`:1200-1212`) and stores **only** title, checksum, size, and mime
— no content extraction, no FTS rows, no embeddings. A non-markdown file is a searchable
filename and nothing more.

Indexing latency is ~1 s (`awatch(debounce=sync_delay)`, `sync_delay: 1000`).

---

## Frontmatter

```yaml
---
title: Selector eligibility bypass in select_for_role
type: verified-fact
status: active
provenance: verdict-core/src/verdict/routing/selector.py:118-134
observed_at: 2026-08-24T14:02:11Z
confidence: verified
tags: [verdict-core, routing, spec-272]
---
```

| Key | Required | Values |
|---|---|---|
| `title` | yes | Kebab-cased by basic-memory into `{project}/{folder}/{kebab-title}`; `permalinks_include_project: true`. Unique per project. |
| `type` | yes | `decision` \| `verified-fact` \| `refuted-claim` \| `correction` \| `session`. The first four are exactly FR-005a's classes; `session` is the capture output. Free text in basic-memory but indexed (`ix_note_type`), so it filters efficiently. |
| `status` | yes | `active` \| `superseded` \| `disputed`. |
| `provenance` | yes | Session id, `path:line-range`, command, or URL. |
| `observed_at` | when known | ISO-8601 Z. Distinct from write time. |
| `confidence` | yes | `verified` \| `reported` \| `inferred`. `verified` = direct observation only. |
| `tags` | no | Free. |

`status`, `provenance`, `observed_at`, and `confidence` come straight from the 2026-08-19
prior-art decision, which already mandates them.

---

## Body

````markdown
## Claim

select_for_role reads from the full candidate pool rather than the eligible subset.

## Evidence

```python
# verdict-core/src/verdict/routing/selector.py:118
candidates = self._all_candidates()   # not self._eligible(role)
```

Spec 272 AC-1.5 requires eligibility filtering before selection.

## Relations

- contradicts [[pilot/facts/selector-honours-eligibility]]
- evidence_for [[pilot/decisions/routing-overhaul]]
````

| Section | Required for |
|---|---|
| `## Claim` | all |
| `## Evidence` | `verified-fact`, `refuted-claim` |
| `## Rationale` | `decision` |
| `## Relations` | any note with relations |

---

## Relations

`[[permalink]]` links. basic-memory's `relation` table has free, indexed `relation_type`, and
`to_name` holds unresolved forward references — **a note may link to one that does not exist
yet**, so a `supersedes` link can be written before the target is created.

| `relation_type` | Meaning |
|---|---|
| `supersedes` / `superseded_by` | Authoritative replacement. Both notes retained. |
| `contradicts` | Mutual, unresolved → both `disputed`. |
| `evidence_for` | Record → the session note that produced it. |

**basic-memory has no native supersede or contradiction concept.** These are conventions this
feature defines and must enforce in its own write path.

---

## Conflict handling (FR-006)

When a new note covers the same subject as an existing one:

- **Authoritative replacement** → new note gains `supersedes`; old is edited to
  `status: superseded` with `superseded_by`. Both retained.
- **Unresolved** → both marked `status: disputed`, linked by `contradicts`.

**No silent merge, no overwrite, no auto-picked winner — including by recency.** Recall
returns both, flagged.

Already demonstrated: the 2026-08-19 benchmark "selected active `cobalt` over superseded
`amber`, reported conflicting Meridian values `42` and `57` as disputed, and rejected
unrelated `tin-lantern` as a negative control."

Mechanically, retention is also the default: `write_note` **errors on an existing identifier**
(`write_note.py:59`, resolution order `:201-205`; `write_note_overwrite_default: false`).
Updates use `edit_note` (`append`, `prepend`, `find_replace`, `replace_section`). There is no
versioning — overwrite genuinely replaces, which is why the write path must never overwrite.

---

## Redaction (FR-014)

**Every byte is redacted before the file is written.** There is no post-hoc removal:
`embed: false` excludes a note from semantic indexing only (`search_service.py:741-763`) and
leaves it fully present in FTS. `embed: false` is a relevance control, never a secrecy
control.

Masked as `⟨redacted:<rule-id>⟩`. Confirmed present in the corpus: `ANTHROPIC_AUTH_TOKEN`,
641 occurrences across 32 files, **152 followed by a real value across 25 files**.

**Fail closed**: if a rendered note still matches any redaction rule, it is not written.

---

## Retrieval

Search is hybrid — FTS5 `search_index` (unicode61) plus `search_vector_embeddings` as
`vec0 float[384]`, model `FastEmbedEmbeddingProvider:bge-small-en-v1.5:384`
(`semantic_vector_k: 100`, `semantic_min_similarity: 0.55`).

`_default_search_type()` (`mcp/tools/search.py:42-55`) returns `hybrid` because
`semantic_search_enabled: true`. **But the service layer falls back to FTS when no mode is
supplied** (`services/search_service.py:201`) — the MCP layer is what supplies `hybrid`.

**Precision-sensitive queries MUST pass `search_type` explicitly**, per both that fallback and
the prior-art note's own conclusion ("search mode should be explicit for benchmarked or
precision-sensitive retrieval").
