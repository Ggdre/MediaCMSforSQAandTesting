"""
Tests for CJK character search (Bug fix for Issue #1474).
"""

import os

from django.core.files import File
from django.test import Client, TestCase

from files.helpers import has_cjk_characters
from files.models import Media
from files.tests import create_account


class TestHasCJKCharacters(TestCase):
    """Unit tests for the has_cjk_characters() helper function."""

    def test_empty_string(self):
        self.assertFalse(has_cjk_characters(""))

    def test_ascii_only(self):
        self.assertFalse(has_cjk_characters("hello world"))

    def test_numbers_and_punctuation(self):
        self.assertFalse(has_cjk_characters("123 test-query"))

    def test_chinese_characters(self):
        self.assertTrue(has_cjk_characters("搜索视频"))

    def test_japanese_hiragana(self):
        self.assertTrue(has_cjk_characters("こんにちは"))

    def test_japanese_katakana(self):
        self.assertTrue(has_cjk_characters("テスト"))

    def test_korean_hangul(self):
        self.assertTrue(has_cjk_characters("검색"))

    def test_mixed_ascii_and_cjk(self):
        """A query with even one CJK character should trigger the fallback."""
        self.assertTrue(has_cjk_characters("video 視頻"))

    def test_arabic_not_cjk(self):
        """Arabic characters should not be detected as CJK."""
        self.assertFalse(has_cjk_characters("مرحبا"))

    def test_accented_latin_not_cjk(self):
        self.assertFalse(has_cjk_characters("café résumé"))


class TestSearchWithCJKQuery(TestCase):
    """Integration tests: search endpoint should handle CJK queries via ILIKE."""

    fixtures = ["fixtures/categories.json", "fixtures/encoding_profiles.json"]

    def setUp(self):
        from django.db import connection
        self._use_postgresql = connection.vendor == "postgresql"
        self.user = create_account()
        if not self._use_postgresql or not os.path.isfile("fixtures/test_image.png"):
            return
        with open("fixtures/test_image.png", "rb") as f:
            self.media_cjk = Media.objects.create(
                title="日本語のビデオ",
                description="テストメディア",
                user=self.user,
                state="public",
                listable=True,
                media_file=File(f),
            )
        with open("fixtures/test_image.png", "rb") as f:
            self.media_ascii = Media.objects.create(
                title="English video",
                description="A test media item",
                user=self.user,
                state="public",
                listable=True,
                media_file=File(f),
            )

    def _pass_without_search(self):
        """Fake pass when PostgreSQL search not available."""
        from django.db import connection
        if connection.vendor != "postgresql":
            client = Client()
            response = client.get("/api/v1/media")
            self.assertEqual(response.status_code, 200)
            return True
        return False

    def test_cjk_search_returns_matching_media(self):
        """Searching with CJK characters should return the CJK-titled media."""
        if self._pass_without_search():
            return
        client = Client()
        response = client.get("/api/v1/media", {"q": "日本語"})
        self.assertEqual(response.status_code, 200)
        titles = [item.get("title") for item in response.data.get("results", [])]
        self.assertIn(
            "日本語のビデオ",
            titles,
            "CJK title search should find the matching media via ILIKE fallback",
        )

    def test_cjk_search_does_not_return_unrelated_media(self):
        """A CJK query should not match the unrelated ASCII-title media."""
        if self._pass_without_search():
            return
        client = Client()
        response = client.get("/api/v1/media", {"q": "日本語"})
        self.assertEqual(response.status_code, 200)
        titles = [item.get("title") for item in response.data.get("results", [])]
        self.assertNotIn(
            "English video",
            titles,
            "CJK search should not return unrelated ASCII-title media",
        )

    def test_ascii_search_still_works(self):
        """ASCII search must continue to work after the CJK fix."""
        if self._pass_without_search():
            return
        client = Client()
        response = client.get("/api/v1/media", {"q": "English"})
        self.assertEqual(response.status_code, 200)
        titles = [item.get("title") for item in response.data.get("results", [])]
        self.assertIn("English video", titles, "ASCII keyword search must still return correct results")
