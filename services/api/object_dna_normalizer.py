from copy import deepcopy
from typing import Any


def _rename_if_missing(
    item: dict[str, Any],
    target: str,
    aliases: tuple[str, ...],
) -> None:
    if target in item:
        return

    for alias in aliases:
        if alias in item:
            item[target] = item.pop(alias)
            return


def normalize_object_dna_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize known model/provider field-name deviations.

    This function only repairs structural aliases.
    It does NOT change the semantic meaning of traits or capabilities.
    """

    data = deepcopy(payload)

    physical_traits = data.get("physical_traits", [])

    if isinstance(physical_traits, list):
        for trait in physical_traits:
            if not isinstance(trait, dict):
                continue

            _rename_if_missing(
                trait,
                "trait",
                ("property",),
            )

            _rename_if_missing(
                trait,
                "evidence_basis",
                ("evidence",),
            )

            _rename_if_missing(
                trait,
                "note",
                ("description", "reason"),
            )

    affordances = data.get("affordances", [])

    if isinstance(affordances, list):
        for affordance in affordances:
            if not isinstance(affordance, dict):
                continue

            # Nemotron Super has occasionally returned "trait"
            # or "property" where our ObjectAffordance schema
            # correctly expects "capability".
            _rename_if_missing(
                affordance,
                "capability",
                ("trait", "property"),
            )

            _rename_if_missing(
                affordance,
                "description",
                ("note", "reason"),
            )

            _rename_if_missing(
                affordance,
                "evidence_basis",
                ("evidence",),
            )

    return data