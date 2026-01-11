"""
Verifiering: datum/tid-maskning ska vara deterministisk och idempotent.
Ingen rå content loggas.
"""

from text_processing import mask_datetime
from text_processing import mask_text_strict


def test_mask_datetime_strict_basic():
    text = "Möte 2026-01-06 13:24."
    masked, stats = mask_datetime(text, level="strict")
    assert masked == "Möte [DATUM] [TID]."
    assert stats["datetime_masked"] is True
    assert stats["datetime_mask_count"] >= 2


def test_mask_datetime_idempotent():
    text = "Möte 2026-01-06 13:24."
    masked1, _ = mask_datetime(text, level="strict")
    masked2, _ = mask_datetime(masked1, level="strict")
    assert masked1 == masked2


def test_strict_pipeline_masks_datetime_before_phone():
    # Regression guard: date/time must never turn into [PHONE] fragments.
    text = "Kontakt: anna.berg@example.com, Tel: 070-123 45 67, Datum: 2026-01-06 13:24."
    masked = mask_text_strict(text)
    assert "[DATUM]" in masked
    assert "[TID]" in masked
    assert "2026" not in masked

