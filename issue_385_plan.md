# Issue #385 — CITATION.cff for nwb2bids output

Plan + context for implementation in a fresh session.

Issue: https://github.com/con/nwb2bids/issues/385 — produce `CITATION.cff`
(adopted by BIDS, see
https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/dataset-description.html#citationcff),
ideally enriched from DANDI dandiset / datacite metadata when available.

## Project conventions to remember (from CLAUDE.md / dev guide)

- Read `docs/developer_guide.rst` and `.github/copilot-instructions.md` first.
- Test categories: `tests/unit/`, `tests/integration/`, `tests/convert_nwb_dataset/` (CLI).
- Assertion style: `assert actual == expected` (actual on left).
- Mark AI-generated tests with `@pytest.mark.ai_generated`.
- Avoid try/except where guards work; max 2–3 levels of nesting; no single-letter vars.
- PR titles in past tense ("Added CITATION.cff …").
- Run `pre-commit run --all-files` before pushing.
- Never expose `_private` symbols from `__init__.py`.
- Keep CLI `help=` strings consistent with API docstrings; first-line docstrings ≤120 chars.
- `ruamel.yaml~=0.18.15` is already a dep but currently unused — use it for YAML output.

## Incoming-data summary (from research spoke)

Two ingest paths in `src/nwb2bids/_converters/_dataset_converter.py`:

- `DatasetConverter.from_nwb_paths()` (line 154) — local NWB files/dirs; user
  supplies optional `additional_metadata_file_path` JSON containing a
  `dataset_description` block.
- `DatasetConverter.from_remote_dandiset()` (line 66) — fetches a dandiset via
  `dandi.dandiapi.DandiAPIClient` and calls `get_bids_dataset_description()`.

Currently extracted from a dandiset (`_converters/_dandi_utils.py`):
`identifier`, `name`, `description`, `contributor` (Person/Author), `license`.

Currently extracted from NWB files (`bids_models/_participant.py`,
`_general_metadata.py`): subject id/species/sex/strain, institution, device,
etc. **No** keywords/lab/experimenter/DOI extraction from NWB itself.

`dataset_description.json` writer: `DatasetConverter.write_dataset_description()`
(line 329) — populates `Name`, `Description`, `Authors`, `License`,
`DatasetType`, `BIDSVersion`, `HEDVersion`, `GeneratedBy`.

## Gap analysis for CITATION.cff fields

| Field           | Source                                                            |
| --------------- | ----------------------------------------------------------------- |
| `cff-version`   | hardcoded `"1.2.0"`                                               |
| `message`       | hardcoded boilerplate (see design decision below)                 |
| `title`         | from `dataset_description.Name`                                   |
| `authors`       | from `dataset_description.Authors` (split `"Last, First"`)        |
| `type`          | hardcoded `"dataset"`                                             |
| `license`       | from `dataset_description.License` (already SPDX-like)            |
| `abstract`      | from `dataset_description.Description`                            |
| `version`       | dandiset `version_id` if present; else omit                       |
| `date-released` | dandiset `datePublished` (Phase 2)                                |
| `keywords`      | dandiset `keywords` (Phase 2)                                     |
| `repository`    | `https://dandiarchive.org/dandiset/{id}` (Phase 2)                |
| `doi`           | dandiset `doi` (Phase 2)                                          |
| `references`    | dandiset `relatedResource` / `relatedPublication` (Phase 2)       |

## Design decisions already agreed with user

1. **Author parsing.** DANDI gives `"Last, First"` strings. Split on `", "` into
   CFF `family-names` + `given-names`. If no comma (e.g. organization name),
   fall back to CFF's single-`name:` entity form.
2. **`message` field.** Hardcode neutral default:
   `"If you use this dataset, please cite it as below."`
3. **Implementation cadence.** Small atomic changes, stop after each, show how
   to test, wait for next prompt. (User's standing rule from `~/.claude/CLAUDE.md`.)

## Open design questions (decide as you go)

- **YAML lib.** `ruamel.yaml` is already a declared dep but not yet imported
  anywhere. Use it (don't add PyYAML).
- **Field naming in pydantic model.** CFF YAML uses kebab-case (`cff-version`,
  `date-released`, `family-names`). Use snake_case Python attrs +
  `pydantic.Field(serialization_alias="kebab-case")` and dump with
  `model_dump(by_alias=True, exclude_none=True)`. Compare against
  `bids_models/_dataset_description.py` for style — note BIDS uses CapitalCase
  attrs directly because that *is* the wire format; CFF differs.
- **Where to put the CITATION.cff writer.** Add `write_citation_cff()` as a
  method on `DatasetConverter` in `_dataset_converter.py`, called from
  `convert_to_bids_dataset()` right after `write_dataset_description()`.
- **What if `dataset_description` is None?** Mirror existing behavior in
  `write_dataset_description` (lines 331–332): construct a minimal default.
  For CITATION.cff, if there's no Name/Authors at all, probably skip writing
  rather than emit a half-empty file. Confirm with user.
- **Phase 2 plumbing.** Easiest path: have `_dandi_utils.get_bids_dataset_description`
  also return a `CitationCff | None` (or a richer dataclass bundle) so dandiset-
  only fields aren't lost on the way to the writer. Or: stash on
  `DatasetConverter` as a separate `citation_cff` attribute populated only by
  `from_remote_dandiset`. The latter is cleaner — the local path won't have
  these fields anyway.

## Implementation plan (atomic steps)

### Phase 1 — local-source CITATION.cff

**Step 1.1 — `bids_models/_citation_cff.py`**
- New pydantic model `CitationCff` (extending `BaseMetadataModel`), plus a
  small `CffAuthor` model with `family_names` / `given_names` / `name` /
  `affiliation` / `orcid` (all optional, but at least one of name OR
  family-names per CFF spec).
- Required CFF fields: `cff_version="1.2.0"`, `message`, `title`, `authors`,
  `type="dataset"`.
- Optional: `version`, `date_released` (date), `license`, `doi`, `url`,
  `repository`, `abstract`, `keywords` (list[str]), `references`.
- `serialization_alias` on each field to produce kebab-case keys.
- Helper classmethod `CffAuthor.from_dandi_name(name: str)` that splits
  `"Last, First"` → `family_names="Last", given_names="First"`; else
  `name=...`.
- Export `CitationCff` from `bids_models/__init__.py`.

**Step 1.2 — `DatasetConverter.write_citation_cff()`**
- New method in `_converters/_dataset_converter.py`. Pull from
  `self.dataset_description` (Name → title, Authors → authors, License →
  license, Description → abstract). Default `version` to nwb2bids version?
  No — that's tool version, not dataset version. Omit when unknown.
- Skip writing entirely if title is None AND authors is empty (no signal).
- Write to `self.run_config.bids_directory / "CITATION.cff"` using
  `ruamel.yaml.YAML(typ="safe")` with `default_flow_style=False`.
- Call from `convert_to_bids_dataset()` between
  `write_dataset_description()` and `write_bidsignore()`.

**Step 1.3 — Tests**
- `tests/unit/test_citation_cff.py` (new):
  - Model round-trip (instantiate → `model_dump(by_alias=True)` → keys).
  - Author splitting: `"Doe, Jane"` → family/given; `"Acme Corp"` → name.
  - Required-field validation (missing title or authors raises).
- Extend `tests/integration/test_convert_nwb_dataset.py` (or add a
  small new file): after a local conversion, assert
  `(bids_dir / "CITATION.cff").exists()` and parse YAML to verify fields
  match the dataset_description input.
- Mark all of these with `@pytest.mark.ai_generated`.

### Phase 2 — DANDI enrichment

**Step 2.1 — extend `_dandi_utils.py`**
- New helper `_get_citation_cff_from_valid_dandiset_metadata(metadata)` that
  pulls: `datePublished` (→ `date_released`), `keywords`, `doi`,
  `relatedResource[*].url` or `identifier` (→ `references`), and constructs
  `repository = f"https://dandiarchive.org/dandiset/{identifier}/{version}"`.
- Mirror `_get_citation_cff_from_invalid_dandiset_metadata(raw_metadata)`
  for the dict path (parallel to existing valid/invalid split).
- Update `get_bids_dataset_description()` to also return `CitationCff | None`,
  or rename → `get_bids_metadata()` returning a small dataclass
  `BidsMetadataBundle(dataset_description, citation_cff, notifications)`.
  (Renaming is cleaner; check callers.)

**Step 2.2 — plumb through DatasetConverter**
- `from_remote_dandiset()` already destructures `get_bids_dataset_description`
  result at line 104. Update to capture `citation_cff` too and assign to
  `dataset_converter.citation_cff` (new optional field on `DatasetConverter`,
  default None).
- `write_citation_cff()` (from Step 1.2) prefers `self.citation_cff` when
  present (it carries the enriched fields), falling back to building from
  `self.dataset_description` for the local path.

**Step 2.3 — tests + spec**
- Unit tests in `tests/unit/test_dandi_utils.py` style: feed fake raw
  metadata dicts, assert enriched fields populate correctly.
- Remote integration test gated by `@pytest.mark.remote` if there's a
  natural fixture dandiset (look at existing
  `tests/unit/test_remote_dataset_converter.py` for the pattern).
- Update `docs/developer_guide.rst` (or whatever doc lists output files) to
  mention `CITATION.cff` in the BIDS root.

## Files to read on session start

- `src/nwb2bids/bids_models/_dataset_description.py` (model pattern)
- `src/nwb2bids/bids_models/_base_metadata_model.py` (base classes)
- `src/nwb2bids/bids_models/__init__.py` (export pattern)
- `src/nwb2bids/_converters/_dataset_converter.py` (writer + flow)
- `src/nwb2bids/_converters/_dandi_utils.py` (DANDI extraction)
- `tests/unit/test_dandi_utils.py` (test pattern, AI marker usage)
- `tests/unit/test_dataset_converter.py` (integration-ish unit pattern)

## Reference: CFF v1.2.0 minimal example

```yaml
cff-version: 1.2.0
message: "If you use this dataset, please cite it as below."
title: "My dataset"
type: dataset
authors:
  - family-names: Doe
    given-names: Jane
    orcid: https://orcid.org/0000-0000-0000-0000
  - name: "Acme Corporation"
license: CC-BY-4.0
doi: 10.5281/zenodo.1234567
date-released: 2026-04-15
version: "1.0.0"
keywords:
  - neuroscience
  - electrophysiology
repository: https://dandiarchive.org/dandiset/000123
```

Spec: https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md

## Tasks already created in tracker

1. Create CitationCff pydantic model
2. Wire CitationCff write into DatasetConverter
3. Phase 1 unit + integration tests
4. Extend dandi_utils with richer extraction
5. Plumb DANDI-enriched fields into CITATION.cff
6. Phase 2 tests + spec update

Tasks may not survive a fresh session — recreate from this list if needed.

## Suggested commit slicing

- Commit 1: Phase 1 model + writer + tests (one PR, label `enhancement` + `minor`).
- Commit 2 (separate PR): Phase 2 DANDI enrichment + tests.

PR title example: `Added CITATION.cff output (closes #385)`.
