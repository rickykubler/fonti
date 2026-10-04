import numpy as np
import pytest

from fonti.config import EmbeddingSettings
from fonti.ml.embedder import HashingEmbedder, create_embedder


def test_hashing_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(dim=64)

    documents = embedder.embed_documents(["Il canone è di euro 800"])
    queries = embedder.embed_queries(["Il canone è di euro 800"])

    np.testing.assert_allclose(documents, queries)
    assert documents.shape == (1, 64)
    assert np.linalg.norm(documents[0]) == pytest.approx(1.0)


def test_hashing_embedder_scores_lexical_overlap_ignoring_accents() -> None:
    embedder = HashingEmbedder()
    documents = embedder.embed_documents(
        ["La libertà personale è inviolabile.", "Il domicilio è inviolabile."]
    )

    scores = documents @ embedder.embed_queries(["liberta personale"])[0]

    assert scores[0] > scores[1]


def test_create_embedder_selects_hashing() -> None:
    assert create_embedder(EmbeddingSettings(model="hashing:128")).model_id == "hashing:128"


def test_model_id_is_known_without_loading_the_model() -> None:
    embedder = create_embedder(EmbeddingSettings(model="BAAI/bge-m3", revision="abc123"))

    assert embedder.model_id == "BAAI/bge-m3@abc123"


@pytest.mark.slow
def test_bge_m3_matches_an_italian_question_to_the_right_article() -> None:
    embedder = create_embedder(EmbeddingSettings(model="BAAI/bge-m3"))
    documents = embedder.embed_documents(
        [
            "La libertà personale è inviolabile. Non è ammessa forma alcuna di detenzione "
            "se non per atto motivato dell'autorità giudiziaria.",
            "Il domicilio è inviolabile. Non vi si possono eseguire ispezioni o perquisizioni.",
        ]
    )

    scores = documents @ embedder.embed_queries(["Quando una persona può essere arrestata?"])[0]

    assert scores[0] > scores[1]
