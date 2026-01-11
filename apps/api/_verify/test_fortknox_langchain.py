from datetime import datetime, timezone

import pytest

from fortknox_langchain import build_langchain_prompt, FortKnoxLangChainConfigError, compile_with_langchain
from schemas import KnoxDocumentItem, KnoxInputPack, KnoxNoteItem, KnoxPolicy, KnoxSourceItem


def _minimal_pack() -> KnoxInputPack:
    policy = KnoxPolicy(
        policy_id="external",
        policy_version="1.0",
        ruleset_hash="external_v1",
        mode="external",
        sanitize_min_level="strict",
        quote_limit_words=8,
        date_strictness="strict",
        max_bytes=200000,
    )
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return KnoxInputPack(
        project={"id": 1, "name": "Test", "tags": None, "status": "research", "created_at": now.isoformat()},
        documents=[
            KnoxDocumentItem(
                doc_id=1,
                sha256="a" * 64,
                sanitize_level="strict",
                updated_at=now,
                masked_text="Detta är en testtext utan PII."
            )
        ],
        notes=[
            KnoxNoteItem(
                note_id=1,
                sha256="b" * 64,
                sanitize_level="strict",
                updated_at=now,
                masked_body="Anteckning utan PII."
            )
        ],
        sources=[
            KnoxSourceItem(source_id=1, type="url", title="Källa")
        ],
        policy=policy,
        template_id="standard",
        input_manifest=[
            {"kind": "document", "id": 1, "sha256": "a" * 64, "sanitize_level": "strict", "updated_at": now.isoformat()},
            {"kind": "note", "id": 1, "sha256": "b" * 64, "sanitize_level": "strict", "updated_at": now.isoformat()},
            {"kind": "source", "id": 1, "type": "url", "title": "Källa"},
        ],
        input_fingerprint="c" * 64,
    )


def test_prompt_is_deterministic():
    pack = _minimal_pack()
    prompt1 = build_langchain_prompt(pack, pack.policy, "standard")
    prompt2 = build_langchain_prompt(pack, pack.policy, "standard")
    assert prompt1 == prompt2
    assert "UNDERLAG (JSON):" in prompt1
    assert pack.input_fingerprint in prompt1


def test_compile_is_fail_closed_when_disabled(monkeypatch):
    pack = _minimal_pack()
    monkeypatch.delenv("FORTKNOX_PIPELINE", raising=False)
    with pytest.raises(FortKnoxLangChainConfigError):
        compile_with_langchain(pack, pack.policy, "standard")

