import datetime
import typing

import pydantic
import typing_extensions

from ._base_metadata_model import BaseMetadataModel


class CffAuthor(BaseMetadataModel):
    """
    Schema for a single author entry in a CITATION.cff file.

    See Also
    --------
    https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md
    """

    family_names: str | None = pydantic.Field(
        description="Family (last) name(s) of an individual author.",
        default=None,
        serialization_alias="family-names",
    )
    given_names: str | None = pydantic.Field(
        description="Given (first) name(s) of an individual author.",
        default=None,
        serialization_alias="given-names",
    )
    name: str | None = pydantic.Field(
        description="Name of an entity (organization, group) author.",
        default=None,
    )
    affiliation: str | None = pydantic.Field(
        description="Affiliation of the author.",
        default=None,
    )
    orcid: str | None = pydantic.Field(
        description="ORCID identifier URL of the author.",
        default=None,
    )

    @pydantic.model_validator(mode="after")
    def validate_at_least_one_identifier(self) -> typing_extensions.Self:
        """CFF requires either an entity `name` or `family-names` for each author."""
        if self.name is None and self.family_names is None:
            message = "CffAuthor requires at least one of `name` or `family_names` to be set."
            raise ValueError(message)
        return self

    @classmethod
    def from_dandi_name(cls, dandi_name: str) -> typing_extensions.Self:
        """
        Build a `CffAuthor` from a DANDI-style name string.

        DANDI exposes person contributors as ``"Last, First"`` strings and organizations as
        single names without a comma. This helper parses the former into ``family_names`` /
        ``given_names`` and falls back to the entity ``name`` form for the latter.

        Parameters
        ----------
        dandi_name : str
            The contributor name string from DANDI metadata.

        Returns
        -------
        CffAuthor
            An instance populated from `dandi_name`.
        """
        if ", " in dandi_name:
            family_names, given_names = dandi_name.split(", ", maxsplit=1)
            return cls(family_names=family_names.strip(), given_names=given_names.strip())
        return cls(name=dandi_name.strip())


class CitationCff(BaseMetadataModel):
    """
    Schema for a CITATION.cff file describing a BIDS dataset produced by `nwb2bids`.

    See Also
    --------
    https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/dataset-description.html#citationcff
    https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md
    """

    cff_version: str = pydantic.Field(
        description="The version of the Citation File Format that this file conforms to.",
        default="1.2.0",
        serialization_alias="cff-version",
    )
    message: str = pydantic.Field(
        description="A message instructing how this dataset should be cited.",
        default="If you use this dataset, please cite it as below.",
    )
    title: str = pydantic.Field(
        description="The title of the dataset being cited.",
    )
    type: typing.Literal["dataset", "software"] = pydantic.Field(
        description="The CFF object type. Always `dataset` for nwb2bids output.",
        default="dataset",
    )
    authors: list[CffAuthor] = pydantic.Field(
        description="List of authors of the dataset.",
        min_length=1,
    )
    version: str | None = pydantic.Field(
        description="The version of the dataset, if known.",
        default=None,
    )
    date_released: datetime.date | None = pydantic.Field(
        description="The date the dataset was released, if known.",
        default=None,
        serialization_alias="date-released",
    )
    license: str | None = pydantic.Field(
        description="SPDX license identifier under which the dataset is released.",
        default=None,
    )
    doi: str | None = pydantic.Field(
        description="The DOI of the dataset, if known.",
        default=None,
    )
    url: str | None = pydantic.Field(
        description="The URL where the dataset can be retrieved.",
        default=None,
    )
    repository: str | None = pydantic.Field(
        description="The URL of a repository that hosts the dataset.",
        default=None,
    )
    abstract: str | None = pydantic.Field(
        description="A short description (abstract) of the dataset.",
        default=None,
    )
    keywords: list[str] | None = pydantic.Field(
        description="Keywords describing the dataset.",
        default=None,
    )
    references: list[dict[str, typing.Any]] | None = pydantic.Field(
        description="List of CFF reference entries for related publications or resources.",
        default=None,
    )
