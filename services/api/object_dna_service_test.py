from object_dna_fixture import OBJECT_DNA_FIXTURE
from object_dna_service import generate_object_dna


item = OBJECT_DNA_FIXTURE.items[0]

result = generate_object_dna(
    item
)

print(
    result.model_dump_json(
        indent=2
    )
)