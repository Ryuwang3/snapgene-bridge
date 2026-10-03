import pytest

from snapgene_bridge.errors import ValidationError
from snapgene_bridge.models import Feature, MoleculeRecord, Primer, Segment


def test_record_uses_normalized_sequence_and_serializes_coordinates():
    record = MoleculeRecord(
        name="fixture",
        sequence="acgt\nacgt",
        features=[
            Feature(
                name="amplicon",
                type="misc_feature",
                segments=(Segment(0, 4),),
            )
        ],
        primers=[Primer(name="fixture-F", sequence="ACGT", binding_start=0, binding_end=4)],
    )

    record.validate()
    data = record.to_dict()

    assert record.sequence == "ACGTACGT"
    assert data["length"] == 8
    assert data["features"][0]["segments"] == [{"start": 0, "end": 4}]
    assert data["primers"][0]["tm_standard"] == "unknown"


def test_invalid_feature_interval_is_rejected():
    record = MoleculeRecord(
        name="fixture",
        sequence="ACGT",
        features=[Feature(name="bad", type="misc_feature", segments=(Segment(0, 9),))],
    )

    with pytest.raises(ValidationError):
        record.validate()


def test_invalid_sequence_symbol_has_actionable_error():
    with pytest.raises(ValidationError, match="unsupported symbols"):
        MoleculeRecord(name="fixture", sequence="ACGT-")


def test_circular_records_allow_origin_spanning_intervals():
    record = MoleculeRecord(
        name="ring",
        sequence="ACGT" * 10,
        topology="circular",
        features=[Feature(name="span", type="misc_feature", segments=(Segment(35, 5),))],
        primers=[Primer(name="P", sequence="ACGTACGT", binding_start=36, binding_end=4)],
    )
    record.validate()
    record.topology = "linear"
    with pytest.raises(ValidationError):
        record.validate()
