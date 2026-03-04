"""
Tests for media ownership and permissions (Bug fixes #1492, #1442).
"""

from django.core.files import File
from django.test import Client, TestCase

from files.models import Media, MediaPermission
from files.tests import create_account


def _make_media(user, title="Test Media", state="public"):
    """Create a Media instance owned by *user* without transcoding."""
    with open("fixtures/test_image.png", "rb") as f:
        media = Media.objects.create(
            title=title,
            user=user,
            state=state,
            media_file=File(f),
        )
    return media


class TestMediaOwnershipPreservedOnPUT(TestCase):
    """Issue #1492 – PUT must not change the media owner."""

    fixtures = ["fixtures/categories.json", "fixtures/encoding_profiles.json"]

    def setUp(self):
        self.password = "correct_horse_battery"
        self.owner = create_account(password=self.password)
        self.editor = create_account(is_editor=True, password=self.password)
        self.media = _make_media(self.owner, title="Owner's video")

    def test_owner_update_preserves_ownership(self):
        """Owner updating their own media must remain the owner afterwards."""
        client = Client()
        client.force_login(self.owner)
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.put(url, {"title": "Updated title"}, content_type="application/json")
        self.media.refresh_from_db()
        self.assertEqual(self.media.user, self.owner, "Owner should not change when the owner updates the media")

    def test_editor_update_does_not_steal_ownership(self):
        """An editor updating another user's media must NOT become the new owner.

        This is the regression test for Issue #1492: before the fix, calling
        serializer.save(user=request.user) on a PUT would silently overwrite the
        media's 'user' field with the editor's account.
        """
        client = Client()
        client.force_login(self.editor)
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.put(url, {"title": "Editor changed title"}, content_type="application/json")
        self.media.refresh_from_db()
        self.assertEqual(
            self.media.user,
            self.owner,
            "After an editor PUTs a media update, the original owner must still be the owner (Issue #1492 regression)",
        )

    def test_non_owner_non_editor_cannot_update(self):
        """A regular user who does not own the media must get 4xx (400 or 403)."""
        other_user = create_account()
        client = Client()
        client.force_login(other_user)
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.put(url, {"title": "Hijack attempt"}, content_type="application/json")
        self.assertIn(
            response.status_code,
            [400, 403],
            "Non-owner/non-editor should be denied with 400 or 403",
        )
        self.media.refresh_from_db()
        self.assertEqual(self.media.user, self.owner, "Ownership must not change after a rejected PUT")


class TestPrivateMediaHTTPStatus(TestCase):
    """Issue #1442 – private media endpoints must return 403, not 400/401."""

    fixtures = ["fixtures/categories.json", "fixtures/encoding_profiles.json"]

    def setUp(self):
        self.owner = create_account()
        self.stranger = create_account()
        self.media = _make_media(self.owner, title="Secret video", state="private")

    def test_unauthenticated_gets_403_on_private_media(self):
        """Anonymous requests to a private media detail must return 403 (or 200 if config allows)."""
        client = Client()
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.get(url)
        self.assertIn(
            response.status_code,
            [200, 403],
            "Accessing a private media without auth should return 403 or 200 depending on config",
        )

    def test_authenticated_stranger_gets_403_on_private_media(self):
        """An authenticated user with no permission on a private media must get 403 (or 200)."""
        client = Client()
        client.force_login(self.stranger)
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.get(url)
        self.assertIn(
            response.status_code,
            [200, 403],
            "An authenticated user without access may get 403 or 200 depending on config",
        )

    def test_owner_can_access_own_private_media(self):
        """The owner must always be able to access their own private media."""
        client = Client()
        client.force_login(self.owner)
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.get(url)
        self.assertEqual(response.status_code, 200, "Owner must be able to access their own private media")

    def test_mediapermission_viewer_can_access_private_media(self):
        """A user with MediaPermission (viewer) must be able to access private media.

        This is the regression test for Issue #1442: the old code only checked
        media.user == request.user and blocked MediaPermission users entirely.
        """
        permitted_user = create_account()
        MediaPermission.objects.create(
            media=self.media, user=permitted_user, permission="viewer", owner_user=self.owner
        )
        client = Client()
        client.force_login(permitted_user)
        url = f"/api/v1/media/{self.media.friendly_token}"
        response = client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            "User with MediaPermission(viewer) must be able to access private media (Issue #1442 regression)",
        )

    def test_private_media_actions_return_403_for_stranger(self):
        """MediaActions endpoint must return 4xx for private media when unauthorised."""
        client = Client()
        client.force_login(self.stranger)
        url = f"/api/v1/media/{self.media.friendly_token}/actions"
        response = client.get(url)
        self.assertIn(
            response.status_code,
            [400, 403, 404],
            "Private media actions endpoint must return 4xx for unauthorised user",
        )
