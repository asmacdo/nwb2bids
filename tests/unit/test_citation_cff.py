"""Unit tests for the `CitationCff` and `CffAuthor` BIDS metadata models."""

import datetime
import io
import pathlib

import pydantic
import pytest
import ruamel.yaml

import nwb2bids
from nwb2bids.bids_models import CffAuthor, CitationCff


@pytest.mark.ai_generated
def test_cff_author_from_dandi_name_person():
    """Author from `Last, First` parses into family/given name fields."""
    author = CffAuthor.from_dandi_name(dandi_name="Doe, Jane")

    assert author.family_names == "Doe"
    assert author.given_names == "Jane"
    assert author.name is None


@pytest.mark.ai_generated
def test_cff_author_from_dandi_name_organization():
    """Author from a single name (no comma) becomes a CFF entity `name`."""
    author = CffAuthor.from_dandi_name(dandi_name="Acme Corporation")

    assert author.name == "Acme Corporation"
    assert author.family_names is None
    assert author.given_names is None


@pytest.mark.ai_generated
def test_cff_author_from_dandi_name_strips_whitespace():
    """Whitespace around split parts is stripped."""
    author = CffAuthor.from_dandi_name(dandi_name="  Doe ,  Jane  ")

    assert author.family_names == "Doe"
    assert author.given_names == "Jane"


@pytest.mark.ai_generated
def test_cff_author_requires_name_or_family_names():
    """A CffAuthor with neither `name` nor `family_names` is rejected."""
    with pytest.raises(pydantic.ValidationError, match="at least one"):
        CffAuthor()


@pytest.mark.ai_generated
def test_citation_cff_minimum_required_fields():
    """`CitationCff` requires `title` and at least one author."""
    citation_cff = CitationCff(title="My Dataset", authors=[CffAuthor.from_dandi_name(dandi_name="Doe, Jane")])

    dump = citation_cff.model_dump(by_alias=True, exclude_none=True)
    expected_dump = {
        "cff-version": "1.2.0",
        "message": "If you use this dataset, please cite it as below.",
        "title": "My Dataset",
        "type": "dataset",
        "authors": [{"family-names": "Doe", "given-names": "Jane"}],
    }
    assert dump == expected_dump


@pytest.mark.ai_generated
def test_citation_cff_missing_title_raises():
    """`CitationCff` rejects missing `title`."""
    with pytest.raises(pydantic.ValidationError, match="title"):
        CitationCff(authors=[CffAuthor.from_dandi_name(dandi_name="Doe, Jane")])


@pytest.mark.ai_generated
def test_citation_cff_empty_authors_raises():
    """`CitationCff` rejects an empty authors list."""
    with pytest.raises(pydantic.ValidationError, match="authors"):
        CitationCff(title="X", authors=[])


@pytest.mark.ai_generated
def test_citation_cff_kebab_case_serialization():
    """Optional fields with snake_case names dump as kebab-case keys."""
    citation_cff = CitationCff(
        title="My Dataset",
        authors=[CffAuthor.from_dandi_name(dandi_name="Doe, Jane")],
        date_released=datetime.date(2026, 1, 15),
        version="1.0.0",
        doi="10.5281/zenodo.1234567",
        keywords=["neuroscience"],
    )

    dump = citation_cff.model_dump(by_alias=True, exclude_none=True)
    assert "date-released" in dump
    assert "date_released" not in dump
    assert dump["date-released"] == datetime.date(2026, 1, 15)
    assert dump["version"] == "1.0.0"
    assert dump["doi"] == "10.5281/zenodo.1234567"
    assert dump["keywords"] == ["neuroscience"]


@pytest.mark.ai_generated
def test_citation_cff_yaml_round_trip():
    """A dumped `CitationCff` can be parsed back into a dictionary with kebab-case keys."""
    citation_cff = CitationCff(
        title="My Dataset",
        authors=[
            CffAuthor.from_dandi_name(dandi_name="Doe, Jane"),
            CffAuthor.from_dandi_name(dandi_name="Acme Corp"),
        ],
        license="CC-BY-4.0",
        abstract="A short description.",
    )
    dump = citation_cff.model_dump(by_alias=True, exclude_none=True)

    yaml = ruamel.yaml.YAML()
    yaml.default_flow_style = False
    buffer = io.StringIO()
    yaml.dump(data=dump, stream=buffer)
    yaml_text = buffer.getvalue()

    reparsed = yaml.load(yaml_text)
    assert reparsed["cff-version"] == "1.2.0"
    assert reparsed["title"] == "My Dataset"
    assert reparsed["type"] == "dataset"
    assert reparsed["authors"] == [
        {"family-names": "Doe", "given-names": "Jane"},
        {"name": "Acme Corp"},
    ]
    assert reparsed["license"] == "CC-BY-4.0"
    assert reparsed["abstract"] == "A short description."


@pytest.mark.ai_generated
def test_dataset_converter_write_citation_cff_from_dataset_description(
    minimal_nwbfile_path: pathlib.Path,
    temporary_bids_directory: pathlib.Path,
    additional_metadata_file_path: pathlib.Path,
):
    """`write_citation_cff` produces a CITATION.cff sourced from `dataset_description`."""
    nwb_paths = [minimal_nwbfile_path]
    run_config = nwb2bids.RunConfig(
        bids_directory=temporary_bids_directory, additional_metadata_file_path=additional_metadata_file_path
    )
    dataset_converter = nwb2bids.DatasetConverter.from_nwb_paths(nwb_paths=nwb_paths, run_config=run_config)
    dataset_converter.extract_metadata()
    dataset_converter.write_citation_cff()

    citation_cff_file_path = temporary_bids_directory / "CITATION.cff"
    assert citation_cff_file_path.exists()

    yaml = ruamel.yaml.YAML()
    citation_cff_dictionary = yaml.load(citation_cff_file_path.read_text())

    assert citation_cff_dictionary["cff-version"] == "1.2.0"
    assert citation_cff_dictionary["title"] == "test"
    assert citation_cff_dictionary["type"] == "dataset"
    assert citation_cff_dictionary["abstract"] == "TODO"
    assert citation_cff_dictionary["license"] == "CC-BY-4.0"
    assert citation_cff_dictionary["authors"] == [{"name": "Cody Baker"}, {"name": "Yaroslav Halchenko"}]


@pytest.mark.ai_generated
def test_dataset_converter_write_citation_cff_skips_when_no_metadata(
    minimal_nwbfile_path: pathlib.Path, temporary_bids_directory: pathlib.Path
):
    """`write_citation_cff` writes nothing when there is no title and no authors."""
    nwb_paths = [minimal_nwbfile_path]
    run_config = nwb2bids.RunConfig(bids_directory=temporary_bids_directory)
    dataset_converter = nwb2bids.DatasetConverter.from_nwb_paths(nwb_paths=nwb_paths, run_config=run_config)
    dataset_converter.write_citation_cff()

    citation_cff_file_path = temporary_bids_directory / "CITATION.cff"
    assert not citation_cff_file_path.exists()


@pytest.mark.ai_generated
def test_dataset_converter_write_citation_cff_prefers_self_citation_cff(
    minimal_nwbfile_path: pathlib.Path, temporary_bids_directory: pathlib.Path
):
    """When `self.citation_cff` is set, it takes precedence over `dataset_description`."""
    nwb_paths = [minimal_nwbfile_path]
    run_config = nwb2bids.RunConfig(bids_directory=temporary_bids_directory)
    dataset_converter = nwb2bids.DatasetConverter.from_nwb_paths(nwb_paths=nwb_paths, run_config=run_config)
    dataset_converter.citation_cff = CitationCff(
        title="Pre-built Title",
        authors=[CffAuthor.from_dandi_name(dandi_name="Smith, John")],
        doi="10.1234/example",
        keywords=["alpha", "beta"],
    )
    dataset_converter.write_citation_cff()

    citation_cff_file_path = temporary_bids_directory / "CITATION.cff"
    assert citation_cff_file_path.exists()

    yaml = ruamel.yaml.YAML()
    citation_cff_dictionary = yaml.load(citation_cff_file_path.read_text())
    assert citation_cff_dictionary["title"] == "Pre-built Title"
    assert citation_cff_dictionary["doi"] == "10.1234/example"
    assert citation_cff_dictionary["keywords"] == ["alpha", "beta"]
    assert citation_cff_dictionary["authors"] == [{"family-names": "Smith", "given-names": "John"}]
