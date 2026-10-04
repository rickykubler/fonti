from pathlib import Path

import pytest

from fonti.ml.hub import ModelUnavailableError, is_cached, load_model


@pytest.fixture
def hub_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "hub"
    monkeypatch.setenv("HF_HUB_CACHE", str(cache))
    repo = cache / "models--org--model"
    (repo / "refs").mkdir(parents=True)
    (repo / "refs" / "main").write_text("abc123", encoding="utf-8")
    (repo / "snapshots" / "abc123").mkdir(parents=True)
    (repo / "snapshots" / "abc123" / "config.json").write_text("{}", encoding="utf-8")
    return cache


def test_is_cached_reads_the_hugging_face_cache_layout(hub_cache: Path, tmp_path: Path) -> None:
    assert is_cached("org/model")
    assert is_cached("org/model", revision="abc123")
    assert not is_cached("org/model", revision="other")
    assert not is_cached("org/missing")
    assert is_cached(str(tmp_path))  # a local folder


def test_cached_models_load_from_disk_only(hub_cache: Path) -> None:
    calls: list[bool] = []

    load_model(calls.append, "org/model", None, offline=False)

    assert calls == [True]


def test_missing_models_are_downloaded_unless_offline(
    hub_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HF_HUB_OFFLINE")  # a fresh process
    calls: list[bool] = []

    load_model(calls.append, "org/missing", None, offline=False)

    assert calls == [False]
    with pytest.raises(ModelUnavailableError, match="models pull"):
        load_model(calls.append, "org/missing", None, offline=True)


def test_missing_model_after_the_process_went_offline_asks_to_pull(hub_cache: Path) -> None:
    # conftest sets HF_HUB_OFFLINE=1, as a cached model loaded earlier would.
    with pytest.raises(ModelUnavailableError, match="models pull"):
        load_model(lambda local_only: None, "org/missing", None, offline=False)


def test_loading_errors_suggest_pulling_the_model(hub_cache: Path) -> None:
    def broken(local_files_only: bool) -> None:
        raise OSError("tokenizer.json not found")

    with pytest.raises(ModelUnavailableError, match=r"tokenizer\.json"):
        load_model(broken, "org/model", None, offline=False)
