"""Unit tests for the `_dandi_utils` module."""

import datetime

import pytest

from nwb2bids._converters._dandi_utils import (
    _build_dandi_repository_url,
    _get_citation_cff_from_invalid_dandiset_metadata,
    _get_dataset_description_from_invalid_dandiset_metadata,
    _parse_iso_date,
)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "contributors, expected_authors",
    [
        pytest.param(
            [
                {"name": "Author, One", "schemaKey": "Person", "roleName": ["dcite:Author"]},
                {"name": "Contact, Two", "schemaKey": "Person", "roleName": ["dcite:ContactPerson"]},
                {"name": "Some Org", "schemaKey": "Organization", "roleName": []},
            ],
            ["Author, One"],
            id="dcite_author_takes_precedence",
        ),
        pytest.param(
            [
                {"name": "Gouwens, Nathan", "schemaKey": "Person", "roleName": ["dcite:ContactPerson"]},
                {"name": "Allen Institute for Brain Science", "schemaKey": "Organization", "roleName": []},
            ],
            ["Gouwens, Nathan"],
            id="fallback_to_persons_excludes_orgs",
        ),
        pytest.param(
            [
                {"name": "Some Organization", "schemaKey": "Organization", "roleName": []},
            ],
            None,
            id="org_only_yields_none",
        ),
    ],
)
def test_author_extraction_from_invalid_metadata(contributors, expected_authors):
    """Author extraction: dcite:Author preferred, then Person fallback (skip Organizations)."""
    raw_metadata = {
        "name": "Test Dandiset",
        "assetsSummary": {"dataStandard": []},
        "contributor": contributors,
    }
    description, _ = _get_dataset_description_from_invalid_dandiset_metadata(raw_metadata=raw_metadata)
    assert description.Authors == expected_authors


@pytest.mark.ai_generated
def test_citation_cff_from_invalid_metadata_full_extraction():
    """All optional CFF fields populate when present in DANDI raw metadata."""
    raw_metadata = {
        "name": "Test Dandiset",
        "identifier": "DANDI:000123",
        "version": "0.250101.1",
        "description": "A demo description.",
        "datePublished": "2026-01-15T00:00:00Z",
        "license": ["spdx:CC-BY-4.0"],
        "doi": "10.48324/dandi.000123/0.250101.1",
        "url": "https://dandiarchive.org/dandiset/000123/0.250101.1",
        "keywords": ["neuroscience", "electrophysiology"],
        "assetsSummary": {"dataStandard": []},
        "contributor": [
            {"name": "Doe, Jane", "schemaKey": "Person", "roleName": ["dcite:Author"]},
            {"name": "Acme Corp", "schemaKey": "Organization", "roleName": []},
        ],
        "relatedResource": [
            {"name": "Companion paper", "url": "https://doi.org/10.1234/x", "identifier": "10.1234/x"},
        ],
    }
    citation_cff, notifications = _get_citation_cff_from_invalid_dandiset_metadata(raw_metadata=raw_metadata)

    assert notifications == []
    assert citation_cff is not None
    assert citation_cff.title == "Test Dandiset"
    assert citation_cff.version == "0.250101.1"
    assert citation_cff.date_released == datetime.date(2026, 1, 15)
    assert citation_cff.license == "CC-BY-4.0"
    assert citation_cff.doi == "10.48324/dandi.000123/0.250101.1"
    assert citation_cff.url == "https://dandiarchive.org/dandiset/000123/0.250101.1"
    assert citation_cff.repository == "https://dandiarchive.org/dandiset/000123/0.250101.1"
    assert citation_cff.abstract == "A demo description."
    assert citation_cff.keywords == ["neuroscience", "electrophysiology"]
    assert citation_cff.references == [
        {"type": "generic", "title": "Companion paper", "url": "https://doi.org/10.1234/x"}
    ]
    assert len(citation_cff.authors) == 1
    assert citation_cff.authors[0].family_names == "Doe"
    assert citation_cff.authors[0].given_names == "Jane"


@pytest.mark.ai_generated
def test_citation_cff_from_invalid_metadata_skipped_when_already_bids():
    """BIDS dandisets return None — no `CITATION.cff` should be emitted by the writer."""
    raw_metadata = {
        "name": "Already BIDS",
        "assetsSummary": {"dataStandard": [{"identifier": "RRID:SCR_016124"}]},
        "contributor": [{"name": "Doe, Jane", "schemaKey": "Person", "roleName": ["dcite:Author"]}],
    }
    citation_cff, notifications = _get_citation_cff_from_invalid_dandiset_metadata(raw_metadata=raw_metadata)

    assert citation_cff is None
    assert notifications == []


@pytest.mark.ai_generated
def test_citation_cff_from_invalid_metadata_skipped_when_no_authors():
    """Without a derivable author list, no CFF is produced."""
    raw_metadata = {
        "name": "Lonely Dandiset",
        "assetsSummary": {"dataStandard": []},
        "contributor": [{"name": "Acme Corp", "schemaKey": "Organization", "roleName": []}],
    }
    citation_cff, _ = _get_citation_cff_from_invalid_dandiset_metadata(raw_metadata=raw_metadata)

    assert citation_cff is None


@pytest.mark.ai_generated
def test_citation_cff_from_invalid_metadata_skips_multi_license():
    """Two or more licenses are intentionally not encoded in CFF (avoid ambiguity)."""
    raw_metadata = {
        "name": "Multi-licensed",
        "assetsSummary": {"dataStandard": []},
        "license": ["spdx:CC-BY-4.0", "spdx:CC0-1.0"],
        "contributor": [{"name": "Doe, Jane", "schemaKey": "Person", "roleName": ["dcite:Author"]}],
    }
    citation_cff, _ = _get_citation_cff_from_invalid_dandiset_metadata(raw_metadata=raw_metadata)

    assert citation_cff is not None
    assert citation_cff.license is None


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "identifier, version, expected_url",
    [
        ("DANDI:000123", "0.250101.1", "https://dandiarchive.org/dandiset/000123/0.250101.1"),
        ("000123", "draft", "https://dandiarchive.org/dandiset/000123/draft"),
        ("DANDI:000123", None, "https://dandiarchive.org/dandiset/000123"),
        (None, "0.1.0", None),
    ],
)
def test_build_dandi_repository_url(identifier, version, expected_url):
    assert _build_dandi_repository_url(identifier=identifier, version=version) == expected_url


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-01-15", datetime.date(2026, 1, 15)),
        ("2026-01-15T12:34:56Z", datetime.date(2026, 1, 15)),
        (datetime.date(2026, 2, 1), datetime.date(2026, 2, 1)),
        (datetime.datetime(2026, 3, 1, 12), datetime.date(2026, 3, 1)),
        (None, None),
        ("not-a-date", None),
        (12345, None),
    ],
)
def test_parse_iso_date(value, expected):
    assert _parse_iso_date(date_value=value) == expected
