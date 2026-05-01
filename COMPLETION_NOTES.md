# Issue #385 — CITATION.cff for nwb2bids output — completion notes

Issue: https://github.com/con/nwb2bids/issues/385

Both Phase 1 (local-source CITATION.cff) and Phase 2 (DANDI enrichment) from
`issue_385_plan.md` are implemented. All 145 non-remote tests pass; pre-commit
(black, ruff, codespell, mypy) is clean.

## What changed

| File | Purpose |
| --- | --- |
| `src/nwb2bids/bids_models/_citation_cff.py` (new) | `CitationCff` and `CffAuthor` pydantic models |
| `src/nwb2bids/bids_models/__init__.py` | Export `CitationCff`, `CffAuthor` |
| `src/nwb2bids/_converters/_dataset_converter.py` | `citation_cff` field on `DatasetConverter`; `write_citation_cff()` and `_build_citation_cff_from_dataset_description()`; call from `convert_to_bids_dataset` |
| `src/nwb2bids/_converters/_dandi_utils.py` | `get_bids_dataset_description` now also returns `CitationCff \| None`; new `_get_citation_cff_from_{valid,invalid}_dandiset_metadata` plus helpers `_build_dandi_repository_url`, `_build_references_from_*`, `_parse_iso_date` |
| `tests/unit/test_citation_cff.py` (new) | 12 unit + integration tests for the model, the writer, and skip behavior |
| `tests/unit/test_dandi_utils.py` | 18 new cases (full extraction, BIDS-already skip, missing authors, multi-license, repo URL builder, ISO date parser) |
| `tests/integration/test_edge_cases.py` | Added `CITATION.cff` to expected file list of `test_convert_nwb_dataset_with_additional_metadata` |
| `docs/conversion_gallery.rst` | New "Citation" section describing the file |

## Path to get there

1. Install — the committed `venv/` is broken in this sandbox (its `bin/python`
   symlinks to `/usr/bin/python`, which doesn't exist). Created `.venv/` with
   `uv venv .venv --python 3.12` and `uv pip install -e ".[all]" pytest pytest-cov pyyaml`.
   Memory note added at `~/.claude/projects/-home-austin-devel-nwb2bids/memory/project_venv.md`.
2. Phase 1.1 — wrote `_citation_cff.py` mirroring the `_dataset_description.py`
   pydantic style. Snake_case attrs + `serialization_alias` for kebab-case wire
   format (`cff-version`, `family-names`, `date-released`). `CffAuthor` validates
   that at least one of `name` or `family_names` is set; `from_dandi_name`
   splits `"Last, First"` and falls back to entity `name` for organizations.
3. Phase 1.2 — added `citation_cff` field to `DatasetConverter` (used as
   override channel for the DANDI-enriched citation), `write_citation_cff()`
   that prefers `self.citation_cff` and falls back to a
   `_build_citation_cff_from_dataset_description()` helper. Skips writing when
   neither title nor authors can be derived. Uses `ruamel.yaml.YAML()`
   (round-trip mode) to preserve insertion order — `typ='safe'` alphabetized
   keys. Hooked into `convert_to_bids_dataset()` between
   `write_dataset_description()` and `write_bidsignore()`.
4. Phase 1.3 — wrote unit + integration tests. Verified the only existing
   integration test that calls `convert_to_bids_dataset` *with*
   `additional_metadata_file_path` (`test_convert_nwb_dataset_with_additional_metadata`)
   needed `CITATION.cff` added to its expected file set; all other integration
   tests use the default no-metadata path which produces no `CITATION.cff`.
5. Phase 2.1 — extended `_dandi_utils.py`. `get_bids_dataset_description`
   return type expanded from a 2-tuple to a 3-tuple — caller in
   `_dataset_converter.py` is the only one and was updated. Helpers parse
   `dateCreated`/`datePublished`, license, keywords, doi, url, version,
   identifier (DANDI: prefix stripped) and emit a canonical
   `https://dandiarchive.org/dandiset/{id}/{version}` repository URL.
   `relatedResource` entries become CFF `references` of `type: generic`.
6. Phase 2.2 — `from_remote_dandiset` now passes `citation_cff` into the new
   field on `DatasetConverter`; the writer prefers it over the local fallback.
7. Phase 2.3 — added unit tests for the invalid-metadata path (the validated
   path uses dandischema models that are awkward to mock cleanly; the
   `metadata.attr` attribute access pattern is exercised indirectly via the
   existing `@pytest.mark.remote` integration tests). Added a "Citation"
   subsection to `docs/conversion_gallery.rst`.
8. Pre-commit — black reformatted two files; codespell flagged "unparseable"
   (replaced with "unparsable").

## Decisions made (no user intervention)

- **YAML lib & mode:** `ruamel.yaml.YAML()` default (round-trip) mode rather
  than `typ="safe"` because safe-mode alphabetizes keys, breaking the
  conventional CFF order (`cff-version`, `message`, `title`, ...).
- **Tuple expansion vs. rename of `get_bids_dataset_description`:** kept the
  function name and expanded the return tuple from 2 → 3 elements. The plan
  suggested renaming was cleaner; with only one in-tree caller, the smaller
  diff won out.
- **CFF references shape:** every `relatedResource` becomes
  `{"type": "generic", "title": <name|url|identifier>, "url": <url>}`. CFF
  `Reference` requires `type` and `title`; `generic` is the catch-all type and
  avoids guessing whether a resource is an article/book/etc. The DANDI
  `relation` enum (e.g. `dcite:IsCitedBy`) is intentionally dropped — CFF has
  no native field for it.
- **Multi-license handling:** when DANDI declares two or more licenses, the
  CFF `license` field is omitted (mirroring the existing `MultipleLicenses`
  notification on `dataset_description`, which also drops the field). Single
  license entries strip the `spdx:` prefix.
- **`License` field type on `CitationCff`:** `str | None`, NOT a literal of
  the two values that `DatasetDescription.License` accepts. CFF allows any
  SPDX identifier; the existing `DatasetDescription` constraint is unrelated.
- **Skip behavior:** if neither title nor authors can be derived, no
  `CITATION.cff` is written (rather than a half-empty stub).
- **`abstract` mapping:** `dataset_description.Description` →
  `citation_cff.abstract` (CFF has no `description`).
- **`type` field:** always `"dataset"` for nwb2bids output. The model does
  allow `"software"` so the same model could later describe nwb2bids itself,
  but no current writer uses that path.
- **Tutorial expected-structure assertions in `docs/tutorials.rst` were not
  updated:** spot-checked, those tutorials don't supply additional metadata,
  so `CITATION.cff` is not produced and the existing assertions remain valid.

## How to verify

```bash
source .venv/bin/activate

# Unit + integration tests for the new feature:
pytest tests/unit/test_citation_cff.py tests/unit/test_dandi_utils.py -vv

# Full non-remote suite:
pytest tests/ \
  --ignore=tests/unit/test_remote_dataset_converter.py \
  --ignore=tests/integration/test_remote_convert_nwb_dataset.py -q

# Lint/type:
pre-commit run --all-files
```

Inspect a generated file by running the integration test in isolation and
peeking at the temp dir, or interactively:

```python
import nwb2bids
from nwb2bids.bids_models import CitationCff, CffAuthor

cff = CitationCff(
    title="Demo",
    authors=[CffAuthor.from_dandi_name(dandi_name="Doe, Jane")],
    keywords=["neuroscience"],
)
print(cff.model_dump(by_alias=True, exclude_none=True))
```

Remote integration (network-gated) — currently relies on the existing
`@pytest.mark.remote` tests in `tests/unit/test_remote_dataset_converter.py`
hitting dandiset 000003. They were not extended to assert the new CFF
content; doing so would require an unmocked dandiset whose metadata exposes
DOI/datePublished/keywords. Recommend revisiting after this PR lands and
choosing a stable published dandiset for the assertion.

## Suggested PR slicing

Per the plan, two PRs:

1. **Phase 1 only** — model, writer (with `citation_cff` field already in
   place but DANDI extraction stubbed-out for Phase 2), Phase 1 tests,
   `test_edge_cases.py` update, docs blurb. Labels: `enhancement`, `minor`.
2. **Phase 2** — `_dandi_utils.py` extraction + plumbing + Phase 2 tests.
   Labels: `enhancement`, `minor`.

Both phases are currently in a single working tree; if you'd like the plan's
two-PR slicing, splitting at the boundary of `_dandi_utils.py` extraction is
straightforward — Phase 2 only adds new symbols and changes one tuple
unpacking site in `_dataset_converter.py`.

## Files NOT touched (and why)

- `tests/unit/test_remote_dataset_converter.py` — remote-marked, skipped here.
  Worth a follow-up to assert `dataset_converter.citation_cff is not None`
  for a stable published dandiset.
- `tests/integration/test_remote_convert_nwb_dataset.py` — same reason.
- `docs/tutorials.rst` — tutorials don't use additional metadata, so no
  `CITATION.cff` is written and no assertions need updating.
