import unittest

from event_helper import EventManagement, FEDORA_HOMESERVER
from event_helper.matrix_utils import normalize_matrix_id
from event_helper.pretix import AttendeeMatrixInformation, question_id_to_header


FAS_HEADER = question_id_to_header("fas")


class TestNormalizeMatrixId(unittest.TestCase):
    """Safe, loss-free normalization of hand-entered Matrix IDs."""

    def test_already_valid_passes_through(self):
        self.assertEqual(
            normalize_matrix_id("@alice:fedora.im"), "@alice:fedora.im"
        )

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(
            normalize_matrix_id("  @alice:fedora.im  "), "@alice:fedora.im"
        )

    def test_lowercases_domain(self):
        # Matrix domains are case-insensitive; attendees often capitalize them.
        self.assertEqual(
            normalize_matrix_id("@alice:Fedora.IM"), "@alice:fedora.im"
        )

    def test_lowercases_localpart(self):
        self.assertEqual(
            normalize_matrix_id("@Alice:fedora.im"), "@alice:fedora.im"
        )

    def test_prepends_missing_at_sign_by_default(self):
        self.assertEqual(
            normalize_matrix_id("alice:fedora.im"), "@alice:fedora.im"
        )

    def test_preserves_non_fedora_homeserver(self):
        # Normalization must not force fedora.im onto otherwise-valid IDs.
        self.assertEqual(
            normalize_matrix_id("@someone:matrix.org"), "@someone:matrix.org"
        )

    def test_none_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id(None)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id("   ")

    def test_internal_space_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id("@har lom:fedora.im")

    def test_missing_colon_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id("alice")

    def test_double_at_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id("@@alice:fedora.im")

    def test_invalid_domain_raises(self):
        with self.assertRaises(ValueError):
            normalize_matrix_id("@alice:-fedora.im")


class _StubLog:
    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


class _StubSelf:
    """Minimal stand-in for EventManagement.

    `_resolve_attendee_matrix_id` only touches `self.log`, so we can exercise it
    as an unbound method without constructing a full maubot Plugin.
    """

    log = _StubLog()


def resolve(attendee):
    return EventManagement._resolve_attendee_matrix_id(_StubSelf(), attendee)


def attendee(matrix_id, fas=None):
    extra = {}
    if fas is not None:
        extra[FAS_HEADER] = fas
    return AttendeeMatrixInformation("ORDER1", matrix_id, extra)


class TestResolveAttendeeMatrixId(unittest.TestCase):
    """Resolution order: normalize supplied ID, else FAS -> @<fas>:fedora.im, else None."""

    def test_valid_id_is_normalized(self):
        self.assertEqual(resolve(attendee("@Alice:Fedora.im")), "@alice:fedora.im")

    def test_valid_non_fedora_id_is_kept(self):
        self.assertEqual(
            resolve(attendee("@someone:matrix.org")), "@someone:matrix.org"
        )

    def test_invalid_id_falls_back_to_fas(self):
        self.assertEqual(
            resolve(attendee("not-a-matrix-id", fas="alice")),
            f"@alice:{FEDORA_HOMESERVER}",
        )

    def test_fas_fallback_strips_at_and_whitespace(self):
        self.assertEqual(
            resolve(attendee("garbage", fas="  @Alice  ")),
            f"@alice:{FEDORA_HOMESERVER}",
        )

    def test_none_id_falls_back_to_fas(self):
        self.assertEqual(
            resolve(attendee(None, fas="alice")), f"@alice:{FEDORA_HOMESERVER}"
        )

    def test_invalid_id_no_fas_returns_none(self):
        self.assertIsNone(resolve(attendee("garbage")))

    def test_invalid_id_empty_fas_returns_none(self):
        self.assertIsNone(resolve(attendee("garbage", fas="   ")))

    def test_invalid_id_and_invalid_fas_returns_none(self):
        # A FAS value that still can't form a valid mxid (contains a space).
        self.assertIsNone(resolve(attendee("garbage", fas="bad name")))


if __name__ == "__main__":
    unittest.main()
