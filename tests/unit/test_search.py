"""US7: contains, time comparison, and/or/not, fixture expectations."""

import unittest

from model import Criterion, Note, ParseError, TimeCompare, parse_criterion, parse_datetime
from tests.fixture import make_fixture


def ids_for(pim, text):
    return [pir.id for pir in pim.search(parse_criterion(text))]


class FixtureSearchTests(unittest.TestCase):
    """US7 search over the acceptance fixture: type, contains, time comparison, and/or/not."""

    def setUp(self):
        self.pim = make_fixture()

    def test_excessive_parenthesis_nesting_is_a_search_error(self):
        """Even excessive nesting is rejected as a criterion error rather than a traceback."""
        with self.assertRaisesRegex(ParseError, "nested too deeply"):
            parse_criterion("(" * 1200 + "type = note" + ")" * 1200)

    def test_type_note(self):
        """`type = note` matches only the Note, Id 1."""
        self.assertEqual(ids_for(self.pim, "type = note"), [1])

    def test_text_contains_casefold(self):
        """`text contains "milk"` is a casefold substring: it matches the Note "Shopping: Milk" (Id 1)."""
        self.assertEqual(ids_for(self.pim, 'text contains "milk"'), [1])

    def test_unqualified_contains_any_text_field(self):
        """Unqualified `contains "ada"` checks every text field and matches both Contacts (Ids 5, 6)."""
        self.assertEqual(ids_for(self.pim, 'contains "ada"'), [5, 6])

    def test_name_contains_ada_matches_both_contacts(self):
        """Contact `name contains "ada"` matches both Contacts named Ada (Ids 5, 6)."""
        self.assertEqual(
            ids_for(self.pim, 'type = contact && name contains "ada"'),
            [5, 6],
        )

    def test_deadline_comparison_skips_missing_deadline(self):
        """`deadline <` matches Task 2 only; Task 3 has no deadline, so the comparison is false."""
        self.assertEqual(
            ids_for(self.pim, "deadline < 2026-11-21T00:00:00+08:00"),
            [2],
        )

    def test_deadline_greater_and_equal(self):
        """`deadline >` and `deadline =` compare instants and both match Task 2."""
        self.assertEqual(
            ids_for(self.pim, "deadline > 2026-11-19T00:00:00+08:00"),
            [2],
        )
        self.assertEqual(
            ids_for(self.pim, "deadline = 2026-11-20T20:00:00+08:00"),
            [2],
        )

    def test_start_greater_than(self):
        """`start > 2026-09-14T00:00` matches only the Event (Id 4)."""
        self.assertEqual(
            ids_for(self.pim, "start > 2026-09-14T00:00:00+08:00"),
            [4],
        )

    def test_quoted_datetime_matches_start(self):
        """A quoted datetime operand is accepted: `start = "...18:30..."` matches the Event (Id 4)."""
        self.assertEqual(
            ids_for(self.pim, 'start = "2026-09-14T18:30:00+08:00"'),
            [4],
        )

    def test_address_and_mobile_contains(self):
        """`address`/`mobile contains` match Contacts 6 and 5; a missing substring gives an empty result."""
        self.assertEqual(ids_for(self.pim, 'address contains "HK"'), [6])
        self.assertEqual(ids_for(self.pim, 'mobile contains "123"'), [5])
        self.assertEqual(ids_for(self.pim, 'address contains "missing"'), [])

    def test_escaped_quote_and_newline_in_contains(self):
        """Escaped quote and newline in a contains literal match new Notes holding those characters."""
        quoted = self.pim.create_note('say "hi"')
        self.assertEqual(ids_for(self.pim, r'text contains "say \"hi\""'), [quoted.id])
        broken = self.pim.create_note("line\nbreak")
        self.assertEqual(ids_for(self.pim, r'text contains "line\nbreak"'), [broken.id])

    def test_deadline_space_separated_datetime(self):
        """A space-separated datetime (`2026-11-21 00:00`) parses as HKT and matches Task 2."""
        self.assertEqual(ids_for(self.pim, "deadline < 2026-11-21 00:00"), [2])

    def test_start_space_separated_offset_datetime(self):
        """A space-separated datetime with `+08:00` offset matches the Event start (Id 4)."""
        self.assertEqual(
            ids_for(self.pim, "start = 2026-09-14 18:30:00+08:00"),
            [4],
        )

    def test_space_separated_datetime_stops_at_and(self):
        """A space-separated datetime ends before `&&`, so the conjunction with `type = task` gives [2]."""
        self.assertEqual(
            ids_for(self.pim, "deadline < 2026-11-21 00:00 && type = task"),
            [2],
        )

    def test_start_equality_with_hkt(self):
        """`start =` an explicit HKT instant matches the Event (Id 4)."""
        self.assertEqual(
            ids_for(self.pim, "start = 2026-09-14T18:30:00+08:00"),
            [4],
        )

    def test_alarm_is_existential(self):
        # absolute 09:00 matches; relative 1 day = 13th 18:30 is not before 18:00
        """`alarm <` matches the Event when any Effective Alarm Time (here the 09:00 absolute) is earlier."""
        self.assertEqual(
            ids_for(self.pim, "alarm < 2026-09-13T18:00:00+08:00"),
            [4],
        )

    def test_description_contains_comp3211(self):
        """`description contains "comp3211"` is casefold and matches the Event (Id 4)."""
        self.assertEqual(
            ids_for(self.pim, 'description contains "comp3211"'),
            [4],
        )

    def test_and_or_not_and_parentheses(self):
        """`||`, `!(...)`, and `&&` before `||` give [1, 2, 3], [1, 2, 3, 4], and [1, 5, 6]."""
        self.assertEqual(
            ids_for(self.pim, "type = task || type = note"),
            [1, 2, 3],
        )
        self.assertEqual(
            ids_for(self.pim, "!(type = contact)"),
            [1, 2, 3, 4],
        )
        self.assertEqual(
            ids_for(self.pim, "type = contact && name contains \"ada\" || type = note"),
            [1, 5, 6],
        )

    def test_syntax_error_raises_parse_error(self):
        """Malformed or empty criteria raise ParseError; the Working Collection is unchanged."""
        with self.assertRaises(ParseError):
            parse_criterion("type =")
        with self.assertRaises(ParseError):
            parse_criterion("deadline << 2026-01-01")
        with self.assertRaises(ParseError):
            parse_criterion('text contains "unterminated')
        with self.assertRaises(ParseError):
            parse_criterion("")
        before = [pir.id for pir in self.pim.all()]
        with self.assertRaises(ParseError):
            self.pim.search(parse_criterion("???"))
        self.assertEqual([pir.id for pir in self.pim.all()], before)


class PrecedenceTests(unittest.TestCase):
    """Criterion operator precedence: `!` binds tighter than `&&`, parentheses group `||`."""

    def test_not_binds_tighter_than_and(self):
        """`!type = note && type = task` parses as `(!note) && task` and matches Tasks 2 and 3."""
        pim = make_fixture()
        # !type = note && type = task  →  (!note) && task
        self.assertEqual(ids_for(pim, "!type = note && type = task"), [2, 3])

    def test_double_not_and_grouped_or(self):
        """`!(!(type = note))` and `(task || note) && note` both match only the Note (Id 1)."""
        pim = make_fixture()
        self.assertEqual(ids_for(pim, "!(!(type = note))"), [1])
        self.assertEqual(
            ids_for(pim, "(type = task || type = note) && type = note"),
            [1],
        )


class ParseErrorTests(unittest.TestCase):
    """parse_criterion rejects unknown types, fields, operators, and incomplete input with ParseError."""

    def test_unknown_type_field_or_operator(self):
        """Unknown type `series`, fields `title`/`due`, and TimeCompare `!=` each raise ParseError."""
        with self.assertRaises(ParseError):
            parse_criterion("type = series")
        with self.assertRaises(ParseError):
            parse_criterion('title contains "x"')
        with self.assertRaises(ParseError):
            parse_criterion("due < 2026-01-01")
        with self.assertRaises(ParseError):
            TimeCompare("deadline", "!=", parse_datetime("2026-01-01T00:00:00+08:00"))

    def test_malformed_type_clause(self):
        """`type > note` and a quoted type `type = "note"` raise ParseError."""
        with self.assertRaises(ParseError):
            parse_criterion("type > note")
        with self.assertRaises(ParseError):
            parse_criterion('type = "note"')

    def test_incomplete_or_stray_tokens(self):
        """Missing operands, stray `&&`, unclosed `(` or quote, and a bad datetime raise ParseError."""
        with self.assertRaises(ParseError):
            parse_criterion("description")
        with self.assertRaises(ParseError):
            parse_criterion("&&")
        with self.assertRaises(ParseError):
            parse_criterion("deadline <")
        with self.assertRaises(ParseError):
            parse_criterion("deadline < not-a-date")
        with self.assertRaises(ParseError):
            parse_criterion("(type = note")
        with self.assertRaises(ParseError):
            parse_criterion('contains "abc\\')
        with self.assertRaises(ParseError):
            parse_criterion("< 1")
        with self.assertRaises(ParseError):
            parse_criterion("deadline <)")

    def test_base_criterion_matches_is_not_implemented(self):
        """The abstract Criterion.matches raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            Criterion().matches(Note(1, "x"))


if __name__ == "__main__":
    unittest.main()
