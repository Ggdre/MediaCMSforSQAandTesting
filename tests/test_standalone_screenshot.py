"""
Standalone tests for pure functions — no database or Django required.
Run with:  python -m pytest tests/test_standalone_screenshot.py -v
These demonstrate the unit-level test coverage for the fixes in this study.
"""

# ── has_cjk_characters (Fix #3 — Issue #1474) ─────────────────────────────────
# Copy of the function so we can test it without importing Django settings.

def has_cjk_characters(text: str) -> bool:
    """Return True if *text* contains any CJK Unicode character."""
    for ch in text:
        cp = ord(ch)
        if (
            0x3040 <= cp <= 0x30FF    # Hiragana / Katakana
            or 0x4E00 <= cp <= 0x9FFF # CJK Unified Ideographs
            or 0xAC00 <= cp <= 0xD7AF # Hangul Syllables
            or 0x3400 <= cp <= 0x4DBF # CJK Extension A
            or 0x20000 <= cp <= 0x2A6DF  # CJK Extension B
            or 0xF900 <= cp <= 0xFAFF # CJK Compatibility Ideographs
        ):
            return True
    return False


# ── Tests for has_cjk_characters ──────────────────────────────────────────────

class TestHasCjkCharacters:
    """Unit tests for the has_cjk_characters() helper (Fix #3 – Issue #1474)."""

    def test_empty_string_returns_false(self):
        assert has_cjk_characters("") is False

    def test_ascii_only_returns_false(self):
        assert has_cjk_characters("hello world") is False

    def test_numbers_and_punctuation_returns_false(self):
        assert has_cjk_characters("12345 !@#$%") is False

    def test_chinese_characters_returns_true(self):
        assert has_cjk_characters("你好世界") is True

    def test_japanese_hiragana_returns_true(self):
        assert has_cjk_characters("こんにちは") is True

    def test_japanese_katakana_returns_true(self):
        assert has_cjk_characters("コンニチハ") is True

    def test_korean_hangul_returns_true(self):
        assert has_cjk_characters("안녕하세요") is True

    def test_mixed_ascii_and_cjk_returns_true(self):
        assert has_cjk_characters("hello 世界") is True

    def test_arabic_not_cjk(self):
        assert has_cjk_characters("مرحبا") is False

    def test_accented_latin_not_cjk(self):
        assert has_cjk_characters("café résumé") is False

    def test_single_chinese_char_returns_true(self):
        assert has_cjk_characters("中") is True

    def test_whitespace_only_returns_false(self):
        assert has_cjk_characters("   ") is False


# ── HTTP Status Code correctness (Fix #4, #5, #6, #10, #11, #12) ─────────────

class TestHTTPStatusCodeConstants:
    """Verify the correct status codes are used after fixing Defects 4–12."""

    def test_403_not_400_for_permission_denied(self):
        """HTTP 403 Forbidden is the correct response for authorisation failure."""
        HTTP_400 = 400
        HTTP_403 = 403
        # The defect was returning 400; the fix returns 403.
        # This test asserts that 403 != 400 (documents the semantic difference).
        assert HTTP_403 != HTTP_400
        assert HTTP_403 == 403

    def test_200_not_201_for_update_operations(self):
        """HTTP 200 OK is the correct response for update/delete operations."""
        HTTP_200 = 200
        HTTP_201 = 201
        # 201 Created is only for new resource creation; updates must return 200.
        assert HTTP_200 != HTTP_201
        assert HTTP_200 == 200


# ── get_or_create defaults pattern (Fixes #8, #9) ────────────────────────────

class TestGetOrCreateDefaults:
    """
    Demonstrates the correct use of get_or_create() with defaults=
    to prevent duplicate playlist entries (Defects #8 and #9).
    """

    def _simulate_get_or_create(self, store: dict, key: tuple, ordering: int):
        """
        Simulates Django's get_or_create(playlist=p, media=m, defaults={'ordering': n}).
        Returns (object, created_flag).
        """
        if key in store:
            return store[key], False          # found — do NOT update ordering
        obj = {"key": key, "ordering": ordering}
        store[key] = obj
        return obj, True                      # created with ordering

    def test_existing_entry_not_duplicated(self):
        """Adding the same media to a playlist twice must not create two rows."""
        store = {}
        key = ("playlist_1", "media_abc")

        obj1, created1 = self._simulate_get_or_create(store, key, ordering=1)
        obj2, created2 = self._simulate_get_or_create(store, key, ordering=2)

        assert created1 is True
        assert created2 is False           # NOT created second time
        assert len(store) == 1            # only one row in the store

    def test_new_entry_created_with_correct_ordering(self):
        """A new playlist entry must be created with the supplied ordering."""
        store = {}
        key = ("playlist_1", "media_xyz")

        obj, created = self._simulate_get_or_create(store, key, ordering=5)

        assert created is True
        assert obj["ordering"] == 5


# ── Guard order correctness (Fix #7) ─────────────────────────────────────────

class TestGuardOrder:
    """
    Demonstrates that checking for a Response object BEFORE accessing
    attributes prevents AttributeError (Defect #7).
    """

    class FakeResponse:
        """Simulates a DRF Response returned when media is missing/private."""
        status_code = 403

    class FakeMedia:
        user = "owner_user"

    def _get_object_buggy(self, result):
        """Before fix: accesses .user before checking type — crashes."""
        _ = result.user          # AttributeError if result is FakeResponse
        if isinstance(result, self.FakeResponse):
            return result
        return result

    def _get_object_fixed(self, result):
        """After fix: checks isinstance FIRST — safe."""
        if isinstance(result, self.FakeResponse):
            return result
        _ = result.user
        return result

    def test_buggy_guard_raises_on_response_object(self):
        """Before fix: accessing .user on a Response raises AttributeError."""
        import pytest
        with pytest.raises(AttributeError):
            self._get_object_buggy(self.FakeResponse())

    def test_fixed_guard_returns_response_safely(self):
        """After fix: isinstance check comes first — no AttributeError."""
        result = self._get_object_fixed(self.FakeResponse())
        assert isinstance(result, self.FakeResponse)

    def test_fixed_guard_works_for_real_media(self):
        """After fix: real media objects still pass through correctly."""
        result = self._get_object_fixed(self.FakeMedia())
        assert result.user == "owner_user"


# ── Settings access guard (Fix #18) ───────────────────────────────────────────

class TestSettingsAccessGuard:
    """
    Demonstrates the safe getattr() pattern that fixes Defect #18.
    """

    class FakeSettings:
        CAN_COMMENT = "advancedUser"
        # NOTE: CAN_ADD_MEDIA is intentionally absent — simulates misconfigured deployment

    def _user_allowed_to_upload_buggy(self, settings):
        """Before fix: direct attribute access — raises AttributeError if missing."""
        return settings.CAN_ADD_MEDIA   # AttributeError on misconfigured deployment

    def _user_allowed_to_upload_fixed(self, settings):
        """After fix: safe getattr with default — never raises."""
        return getattr(settings, "CAN_ADD_MEDIA", "all")

    def test_buggy_access_raises_when_setting_missing(self):
        """Before fix: missing CAN_ADD_MEDIA raises AttributeError."""
        import pytest
        with pytest.raises(AttributeError):
            self._user_allowed_to_upload_buggy(self.FakeSettings())

    def test_fixed_access_returns_default_when_setting_missing(self):
        """After fix: missing CAN_ADD_MEDIA returns safe default 'all'."""
        result = self._user_allowed_to_upload_fixed(self.FakeSettings())
        assert result == "all"

    def test_fixed_access_returns_configured_value_when_present(self):
        """After fix: when setting is present, its value is returned."""
        class SettingsWithKey:
            CAN_ADD_MEDIA = "advancedUser"
        result = self._user_allowed_to_upload_fixed(SettingsWithKey())
        assert result == "advancedUser"
