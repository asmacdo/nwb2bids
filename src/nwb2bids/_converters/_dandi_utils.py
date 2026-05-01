import datetime
import typing

import pydantic

from ..bids_models import CffAuthor, CitationCff, DatasetDescription
from ..bids_models._model_globals import _BIDS_RRID
from ..notifications import Notification


def get_bids_dataset_description(
    dandiset,
) -> tuple[DatasetDescription | None, CitationCff | None, list[Notification]]:
    """
    Build the BIDS dataset description and CITATION.cff metadata from a DANDI dandiset.

    Returns a 3-tuple of `(dataset_description, citation_cff, notifications)`. Either of the first
    two may be ``None`` (e.g. when the dandiset already declares itself as BIDS, or when the source
    metadata lacks the required fields).
    """
    valid_or_raw: typing.Literal["raw", "valid"] = "valid"
    try:
        metadata = dandiset.get_metadata()
    except pydantic.ValidationError:
        raw_metadata = dandiset.get_raw_metadata()
        valid_or_raw = "raw"

    notifications: list[Notification] = []
    if valid_or_raw == "valid":
        dataset_description, internal_messages = _get_dataset_description_from_valid_dandiset_metadata(
            metadata=metadata
        )
        notifications.extend(internal_messages)
        citation_cff, citation_cff_messages = _get_citation_cff_from_valid_dandiset_metadata(metadata=metadata)
        notifications.extend(citation_cff_messages)
    else:
        dataset_description, internal_messages = _get_dataset_description_from_invalid_dandiset_metadata(
            raw_metadata=raw_metadata
        )
        notifications.extend(internal_messages)
        citation_cff, citation_cff_messages = _get_citation_cff_from_invalid_dandiset_metadata(
            raw_metadata=raw_metadata
        )
        notifications.extend(citation_cff_messages)

        notification = Notification.from_definition(identifier="InvalidDandisetMetadata")
        notifications.append(notification)

    return dataset_description, citation_cff, notifications


def _get_dataset_description_from_valid_dandiset_metadata(
    metadata: typing.Any,
) -> tuple[DatasetDescription | None, list[Notification]]:
    dataset_description_kwargs = dict()

    dandiset_identifier = getattr(metadata, "identifier", "??????")
    dataset_description_kwargs["Name"] = getattr(metadata, "name", f"DANDI Archive Dandiset {dandiset_identifier}")
    dataset_description_kwargs["BIDSVersion"] = "1.10"
    dataset_description_kwargs["HEDVersion"] = "8.3.0"

    notifications = []
    if any(data_standard.identifier == _BIDS_RRID for data_standard in metadata.assetsSummary.dataStandard):
        notification = Notification.from_definition(identifier="DandisetAlreadyBIDS")
        notifications.append(notification)
        return None, notifications

    if metadata.description is not None:
        dataset_description_kwargs["Description"] = metadata.description
    if metadata.contributor is not None:
        authors = [
            contributor.name
            for contributor in metadata.contributor
            for role in contributor.roleName
            if role.value == "dcite:Author"
        ]
        if not authors:
            authors = [contributor.name for contributor in metadata.contributor if contributor.schemaKey == "Person"]
        dataset_description_kwargs["Authors"] = authors
    if metadata.license is not None:
        dataset_description_kwargs["License"] = metadata.license[0].value.split(":")[1]

    dataset_description = DatasetDescription(**dataset_description_kwargs)
    return dataset_description, notifications


def _get_dataset_description_from_invalid_dandiset_metadata(
    raw_metadata: dict[str, typing.Any],
) -> tuple[DatasetDescription | None, list[Notification]]:
    dataset_description_kwargs = dict()

    dandiset_identifier = raw_metadata.get("identifier", "??????")
    dataset_description_kwargs["Name"] = raw_metadata.get("name", f"DANDI Archive Dandiset {dandiset_identifier}")
    dataset_description_kwargs["BIDSVersion"] = "1.10"
    dataset_description_kwargs["HEDVersion"] = "8.3.0"

    assets_summary = raw_metadata.get("assetsSummary", dict())
    data_standards = assets_summary.get("dataStandard", [])

    notifications = []
    if any(data_standard.get("identifier", "") == _BIDS_RRID for data_standard in data_standards):
        notification = Notification.from_definition(identifier="DandisetAlreadyBIDS")
        notifications.append(notification)
        return None, notifications

    dandiset_description = raw_metadata.get("description", None)
    if dandiset_description is not None:
        dataset_description_kwargs["Description"] = dandiset_description

    bids_authors = []
    dandiset_contributors = raw_metadata.get("contributor", [])
    for contributor in dandiset_contributors:
        contributor_name = contributor.get("name", None)
        is_author = "dcite:Author" in contributor.get("roleName", [])
        if contributor_name is not None and is_author:
            bids_authors.append(contributor_name)

    if not bids_authors:
        for contributor in dandiset_contributors:
            contributor_name = contributor.get("name", None)
            if contributor_name is not None and contributor.get("schemaKey", "") == "Person":
                bids_authors.append(contributor_name)

    if bids_authors:
        dataset_description_kwargs["Authors"] = bids_authors

    license = raw_metadata.get("license", [])
    if len(license) > 0:
        if len(license) == 1:
            dataset_description_kwargs["License"] = license[0].split(":")[-1]
        else:
            notification = Notification.from_definition(identifier="MultipleLicenses")
            notifications.append(notification)

    dataset_description = DatasetDescription(**dataset_description_kwargs)
    return dataset_description, notifications


def _get_citation_cff_from_valid_dandiset_metadata(
    metadata: typing.Any,
) -> tuple[CitationCff | None, list[Notification]]:
    """Build a `CitationCff` from a validated dandischema `Dandiset`/`PublishedDandiset` model."""
    notifications: list[Notification] = []

    if any(data_standard.identifier == _BIDS_RRID for data_standard in metadata.assetsSummary.dataStandard):
        return None, notifications

    title = getattr(metadata, "name", None)
    contributors = getattr(metadata, "contributor", None) or []
    author_names = [
        contributor.name
        for contributor in contributors
        for role in contributor.roleName
        if role.value == "dcite:Author"
    ]
    if not author_names:
        author_names = [contributor.name for contributor in contributors if contributor.schemaKey == "Person"]

    if title is None or not author_names:
        return None, notifications

    authors = [CffAuthor.from_dandi_name(dandi_name=name) for name in author_names]

    citation_cff_kwargs: dict[str, typing.Any] = {"title": title, "authors": authors}

    description = getattr(metadata, "description", None)
    if description is not None:
        citation_cff_kwargs["abstract"] = description

    license_entries = getattr(metadata, "license", None) or []
    if len(license_entries) == 1:
        citation_cff_kwargs["license"] = license_entries[0].value.split(":")[1]

    keywords = getattr(metadata, "keywords", None)
    if keywords:
        citation_cff_kwargs["keywords"] = list(keywords)

    doi = getattr(metadata, "doi", None)
    if doi:
        citation_cff_kwargs["doi"] = doi

    url = getattr(metadata, "url", None)
    if url is not None:
        citation_cff_kwargs["url"] = str(url)

    date_published = getattr(metadata, "datePublished", None)
    if date_published is not None:
        citation_cff_kwargs["date_released"] = date_published.date()

    version = getattr(metadata, "version", None)
    if version:
        citation_cff_kwargs["version"] = version

    identifier = getattr(metadata, "identifier", None)
    repository = _build_dandi_repository_url(identifier=identifier, version=version)
    if repository is not None:
        citation_cff_kwargs["repository"] = repository

    related_resources = getattr(metadata, "relatedResource", None) or []
    references = _build_references_from_valid_resources(resources=related_resources)
    if references:
        citation_cff_kwargs["references"] = references

    return CitationCff(**citation_cff_kwargs), notifications


def _get_citation_cff_from_invalid_dandiset_metadata(
    raw_metadata: dict[str, typing.Any],
) -> tuple[CitationCff | None, list[Notification]]:
    """Build a `CitationCff` from a raw DANDI metadata dict (validation-error fallback)."""
    notifications: list[Notification] = []

    assets_summary = raw_metadata.get("assetsSummary", dict())
    data_standards = assets_summary.get("dataStandard", [])
    if any(data_standard.get("identifier", "") == _BIDS_RRID for data_standard in data_standards):
        return None, notifications

    title = raw_metadata.get("name", None)
    contributors = raw_metadata.get("contributor", []) or []

    author_names = []
    for contributor in contributors:
        contributor_name = contributor.get("name", None)
        is_author = "dcite:Author" in contributor.get("roleName", [])
        if contributor_name is not None and is_author:
            author_names.append(contributor_name)
    if not author_names:
        for contributor in contributors:
            contributor_name = contributor.get("name", None)
            if contributor_name is not None and contributor.get("schemaKey", "") == "Person":
                author_names.append(contributor_name)

    if title is None or not author_names:
        return None, notifications

    authors = [CffAuthor.from_dandi_name(dandi_name=name) for name in author_names]
    citation_cff_kwargs: dict[str, typing.Any] = {"title": title, "authors": authors}

    description = raw_metadata.get("description", None)
    if description is not None:
        citation_cff_kwargs["abstract"] = description

    license_entries = raw_metadata.get("license", []) or []
    if len(license_entries) == 1:
        citation_cff_kwargs["license"] = license_entries[0].split(":")[-1]

    keywords = raw_metadata.get("keywords", None)
    if keywords:
        citation_cff_kwargs["keywords"] = list(keywords)

    doi = raw_metadata.get("doi", None)
    if doi:
        citation_cff_kwargs["doi"] = doi

    url = raw_metadata.get("url", None)
    if url:
        citation_cff_kwargs["url"] = str(url)

    date_published = raw_metadata.get("datePublished", None)
    parsed_date = _parse_iso_date(date_value=date_published)
    if parsed_date is not None:
        citation_cff_kwargs["date_released"] = parsed_date

    version = raw_metadata.get("version", None)
    if version:
        citation_cff_kwargs["version"] = version

    identifier = raw_metadata.get("identifier", None)
    repository = _build_dandi_repository_url(identifier=identifier, version=version)
    if repository is not None:
        citation_cff_kwargs["repository"] = repository

    related_resources = raw_metadata.get("relatedResource", []) or []
    references = _build_references_from_raw_resources(resources=related_resources)
    if references:
        citation_cff_kwargs["references"] = references

    return CitationCff(**citation_cff_kwargs), notifications


def _build_dandi_repository_url(identifier: str | None, version: str | None) -> str | None:
    """Construct the canonical dandiarchive.org repository URL when both identifier and version exist."""
    if identifier is None:
        return None
    bare_identifier = identifier.split(":", maxsplit=1)[1] if identifier.startswith("DANDI:") else identifier
    if not version:
        return f"https://dandiarchive.org/dandiset/{bare_identifier}"
    return f"https://dandiarchive.org/dandiset/{bare_identifier}/{version}"


def _build_references_from_valid_resources(resources: list) -> list[dict[str, typing.Any]]:
    """Map dandischema `Resource` entries to CFF reference dicts (only when title or URL is present)."""
    references: list[dict[str, typing.Any]] = []
    for resource in resources:
        title = getattr(resource, "name", None)
        url = getattr(resource, "url", None)
        identifier = getattr(resource, "identifier", None)
        reference = _build_reference_dict(title=title, url=url, identifier=identifier)
        if reference is not None:
            references.append(reference)
    return references


def _build_references_from_raw_resources(resources: list[dict[str, typing.Any]]) -> list[dict[str, typing.Any]]:
    """Map raw DANDI resource dicts to CFF reference dicts (only when title or URL is present)."""
    references: list[dict[str, typing.Any]] = []
    for resource in resources:
        title = resource.get("name", None)
        url = resource.get("url", None)
        identifier = resource.get("identifier", None)
        reference = _build_reference_dict(title=title, url=url, identifier=identifier)
        if reference is not None:
            references.append(reference)
    return references


def _build_reference_dict(title: str | None, url: typing.Any, identifier: str | None) -> dict[str, typing.Any] | None:
    """Build a single CFF reference entry; return None if there is no usable signal."""
    url_string = str(url) if url is not None else None
    chosen_title = title or url_string or identifier
    if chosen_title is None:
        return None
    reference: dict[str, typing.Any] = {"type": "generic", "title": chosen_title}
    if url_string is not None:
        reference["url"] = url_string
    return reference


def _parse_iso_date(date_value: typing.Any) -> datetime.date | None:
    """Return a `datetime.date` from an ISO 8601 date or datetime string, or None when unparsable."""
    if date_value is None:
        return None
    if isinstance(date_value, datetime.datetime):
        return date_value.date()
    if isinstance(date_value, datetime.date):
        return date_value
    if not isinstance(date_value, str):
        return None
    iso_string = date_value.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(iso_string).date()
    except ValueError:
        return None
