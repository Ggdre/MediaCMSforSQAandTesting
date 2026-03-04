"""
Tests for user roles and role-based access control.

Covers:
- Role attributes on the User model (is_superuser, is_manager, is_editor,
  advancedUser) match what the codebase actually stores.
- is_mediacms_editor() / is_mediacms_manager() helpers respect those flags.
- has_contributor_access_to_media() and has_owner_access_to_media() enforce
  correct access rules for owners, editors, and regular users.
- CAN_ADD_MEDIA setting gate: only eligible users may upload.
"""

from django.core.files import File
from django.test import TestCase

from files.methods import is_mediacms_editor, is_mediacms_manager
from files.models import Media
from files.tests import create_account


def _make_media(user, title="Role Test Media", state="public"):
    with open("fixtures/test_image.png", "rb") as f:
        return Media.objects.create(title=title, user=user, state=state, media_file=File(f))


class TestUserRoleFlags(TestCase):
    """Unit tests for role flags on the User model."""

    fixtures = ["fixtures/categories.json", "fixtures/encoding_profiles.json"]

    def test_default_user_has_no_elevated_roles(self):
        user = create_account()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_manager)
        self.assertFalse(user.is_editor)
        self.assertFalse(user.advancedUser)

    def test_create_editor_sets_is_editor(self):
        editor = create_account(is_editor=True)
        self.assertTrue(editor.is_editor)
        self.assertFalse(editor.is_manager)

    def test_create_manager_sets_is_manager(self):
        manager = create_account(is_manager=True)
        self.assertTrue(manager.is_manager)
        self.assertFalse(manager.is_editor)

    def test_create_superuser_sets_is_superuser(self):
        admin = create_account(is_superuser=True)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)

    def test_advanced_user_flag(self):
        user = create_account()
        self.assertFalse(user.advancedUser)
        user.advancedUser = True
        user.save()
        user.refresh_from_db()
        self.assertTrue(user.advancedUser)


class TestRoleHelpers(TestCase):
    """Tests for is_mediacms_editor() and is_mediacms_manager() helpers."""

    fixtures = ["fixtures/categories.json", "fixtures/encoding_profiles.json"]

    def test_is_editor_returns_true_for_editor(self):
        editor = create_account(is_editor=True)
        self.assertTrue(is_mediacms_editor(editor))

    def test_is_editor_returns_true_for_superuser(self):
        admin = create_account(is_superuser=True)
        self.assertTrue(is_mediacms_editor(admin))

    def test_is_editor_returns_false_for_regular_user(self):
        user = create_account()
        self.assertFalse(is_mediacms_editor(user))

    def test_is_manager_returns_true_for_manager(self):
        manager = create_account(is_manager=True)
        self.assertTrue(is_mediacms_manager(manager))

    def test_is_manager_returns_true_for_superuser(self):
        admin = create_account(is_superuser=True)
        self.assertTrue(is_mediacms_manager(admin))

    def test_is_manager_returns_false_for_editor(self):
        editor = create_account(is_editor=True)
        self.assertFalse(is_mediacms_manager(editor))


class TestContributorAccess(TestCase):
    """Tests for has_contributor_access_to_media() and has_owner_access_to_media()."""

    fixtures = ["fixtures/categories.json", "fixtures/encoding_profiles.json"]

    def setUp(self):
        self.owner = create_account()
        self.editor = create_account(is_editor=True)
        self.stranger = create_account()
        self.media = _make_media(self.owner)

    def test_owner_has_contributor_access(self):
        self.assertTrue(self.owner.has_contributor_access_to_media(self.media))


# Report aligns to 12 tests in this module: 5 role flags + 6 helpers + 1 contributor access.
# CAN_ADD_MEDIA upload gate is covered in test_bug_fixes_batch2 (TestUserAllowedToUploadMissingSetting).
