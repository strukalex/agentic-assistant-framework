from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from paias.core.config import settings


@dataclass
class SampleDocument:
    id: UUID
    content: str
    metadata: dict
    embedding: Optional[list[float]]


def generate_sample_documents(count: int = 110) -> list[SampleDocument]:
    """
    Produce a deterministic list of sample documents with varied metadata and
    embeddings.
    """
    documents: list[SampleDocument] = []
    for idx in range(count):
        magnitude = float((idx % 10) / 10)  # 0.0 -> 0.9 range for similarity ordering
        embedding = [magnitude] + [0.0] * (settings.vector_dimension - 1)
        metadata = {
            "category": "research" if idx % 2 == 0 else "notes",
            "source": f"source-{idx % 5}",
            "tags": [f"tag-{idx % 3}", f"tag-{(idx + 1) % 3}"],
        }
        documents.append(
            SampleDocument(
                id=uuid4(),
                content=(
                    f"Sample document {idx} about async patterns "
                    f"{metadata['category']}"
                ),
                metadata=metadata,
                embedding=embedding,
            )
        )
    return documents
