"""Composite Search Criterion and the US7 parser.

`parse_criterion` lives here so search is unit-testable without the View.
"""

from __future__ import annotations

from datetime import datetime, timezone

from model.pir import PIR, ParseError, TYPE_NAMES, parse_datetime

TEXT_FIELDS = frozenset({"text", "description", "name", "address", "mobile"})
TIME_FIELDS = frozenset({"deadline", "start", "alarm"})
OPS = {"=": lambda a, b: a == b, "<": lambda a, b: a < b, ">": lambda a, b: a > b}
MAX_NESTING = 100


class Criterion:
    """One node of a search tree."""

    def matches(self, pir: PIR) -> bool:
        """True iff `pir` satisfies this node."""
        raise NotImplementedError


class TypeIs(Criterion):
    """True when the PIR's type equals `type_name`."""

    def __init__(self, type_name: str):
        name = type_name.casefold()
        if name not in TYPE_NAMES:
            raise ParseError(f"unknown type: {type_name}")
        self.type_name = name

    def matches(self, pir: PIR) -> bool:
        """True when the PIR is of this type."""
        return pir.type_name == self.type_name


class Contains(Criterion):
    """Substring after str.casefold(). field is None for unqualified contains."""

    def __init__(self, field: str | None, needle: str):
        if field is None:
            self.field = None
        else:
            key = field.casefold()
            if key not in TEXT_FIELDS:
                raise ParseError(f"unknown text field: {field}")
            self.field = key
        self.needle = needle.casefold()

    def matches(self, pir: PIR) -> bool:
        """True when the named field, or any text field when unqualified, contains the needle after case folding."""
        if self.field is None:
            return any(self.needle in text.casefold() for text in pir.text_fields())
        value = pir.text_value(self.field)
        if value is None:
            return False
        return self.needle in value.casefold()


class TimeCompare(Criterion):
    """True when any instant of `field` satisfies `op` against `instant`. A missing field is false."""

    def __init__(self, field: str, op: str, instant: datetime):
        key = field.casefold()
        if key not in TIME_FIELDS:
            raise ParseError(f"unknown time field: {field}")
        if op not in OPS:
            raise ParseError(f"unknown comparison: {op}")
        self.field = key
        self.op = op
        self.instant = parse_datetime(instant).astimezone(timezone.utc)

    def matches(self, pir: PIR) -> bool:
        """True when any instant of the field satisfies the comparison; false if the PIR has none."""
        values = pir.time_values(self.field)
        if not values:
            return False
        compare = OPS[self.op]
        return any(compare(value.astimezone(timezone.utc), self.instant) for value in values)


class And(Criterion):
    """Both sides match."""

    def __init__(self, left: Criterion, right: Criterion):
        self.left = left
        self.right = right

    def matches(self, pir: PIR) -> bool:
        """True when both sub-criteria match."""
        return _matches_tree(self, pir)


class Or(Criterion):
    """Either side matches."""

    def __init__(self, left: Criterion, right: Criterion):
        self.left = left
        self.right = right

    def matches(self, pir: PIR) -> bool:
        """True when either sub-criterion matches."""
        return _matches_tree(self, pir)


class Not(Criterion):
    """Inner does not match."""

    def __init__(self, inner: Criterion):
        self.inner = inner

    def matches(self, pir: PIR) -> bool:
        """True when the inner criterion does not match."""
        return _matches_tree(self, pir)


def _matches_tree(tree: Criterion, pir: PIR) -> bool:
    """Evaluate Boolean nodes without using the Python call stack, preserving short-circuiting."""
    pending = [(tree, False)]
    result = False
    while pending:
        node, evaluated_child = pending.pop()
        if isinstance(node, Not):
            if evaluated_child:
                result = not result
            else:
                pending.extend(((node, True), (node.inner, False)))
        elif isinstance(node, (And, Or)):
            if not evaluated_child:
                pending.extend(((node, True), (node.left, False)))
            elif result == isinstance(node, And):
                pending.append((node.right, False))
        else:
            result = node.matches(pir)
    return result


def parse_criterion(text: str) -> Criterion:
    """Parse one US7 criterion line. Raises ParseError on empty input or bad syntax."""
    if text is None or not str(text).strip():
        raise ParseError("search criterion is required")
    parser = _Parser(tokenize(text))
    tree = parser.parse_or(0)
    parser.expect("EOF")
    return tree


def tokenize(text: str) -> list[tuple[str, str]]:
    """Lex a criterion line into (kind, value) tokens, ending with EOF."""
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("&&", i):
            tokens.append(("AND", "&&"))
            i += 2
            continue
        if text.startswith("||", i):
            tokens.append(("OR", "||"))
            i += 2
            continue
        if ch == "!":
            tokens.append(("NOT", "!"))
            i += 1
            continue
        if ch == "(":
            tokens.append(("LPAREN", "("))
            i += 1
            continue
        if ch == ")":
            tokens.append(("RPAREN", ")"))
            i += 1
            continue
        if ch in "<>=":
            tokens.append(("CMP", ch))
            i += 1
            # Time operands may contain spaces (`YYYY-MM-DD HH:MM`); stop at
            # `&&`, `||`, `)`, or end so they stay one TIME token.
            if _follows_time_field(tokens):
                i = _consume_datetime(text, i, tokens)
            continue
        if ch == '"':
            value, i = _read_string(text, i)
            tokens.append(("STRING", value))
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            if word.casefold() == "contains":
                tokens.append(("CONTAINS", word))
            else:
                tokens.append(("IDENT", word))
            i = j
            continue
        j = i + 1
        while j < n and not text[j].isspace() and text[j] not in "()!<>=" and not text.startswith("&&", j) and not text.startswith("||", j):
            j += 1
        tokens.append(("TIME", text[i:j]))
        i = j
    tokens.append(("EOF", ""))
    return tokens


def _follows_time_field(tokens: list[tuple[str, str]]) -> bool:
    """True when the last two tokens are a time field and a comparison, so a datetime comes next."""
    if len(tokens) < 2:
        return False
    kind, value = tokens[-2]
    return kind == "IDENT" and value.casefold() in TIME_FIELDS


def _consume_datetime(text: str, i: int, tokens: list[tuple[str, str]]) -> int:
    """Append an unquoted datetime as one TIME token, up to `&&`, `||`, or `)`.

    Returns the index after it, or `i` unchanged when the value is quoted or missing.
    """
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] == '"':
        return i
    j = i
    while j < n:
        if text.startswith("&&", j) or text.startswith("||", j) or text[j] == ")":
            break
        j += 1
    raw = text[i:j].rstrip()
    if raw:
        tokens.append(("TIME", raw))
        return j
    return i


def _read_string(text: str, start: int) -> tuple[str, int]:
    """Read a quoted string starting at `start`; returns its value and the index after it.

    Backslash escapes the next character (`\\n` is a newline). Raises ParseError if unterminated.
    """
    i = start + 1
    chars: list[str] = []
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 1
            if i >= n:
                raise ParseError("unterminated string")
            escaped = text[i]
            if escaped == "n":
                chars.append("\n")
            else:
                chars.append(escaped)
            i += 1
            continue
        if ch == '"':
            return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    raise ParseError("unterminated string")


class _Parser:
    """Recursive-descent parser over a token list; precedence is `!` > `&&` > `||`."""

    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> tuple[str, str]:
        """The current token without consuming it."""
        return self.tokens[self.index]

    def peek_kind(self) -> str:
        """The kind of the current token."""
        return self.peek()[0]

    def take(self) -> tuple[str, str]:
        """Consume and return the current token."""
        token = self.peek()
        self.index += 1
        return token

    def expect(self, kind: str) -> tuple[str, str]:
        """Consume a token of `kind`; raise ParseError if the next token is another kind."""
        got = self.take()
        if got[0] != kind:
            raise ParseError(f"expected {kind}, got {got[1]!r}")
        return got

    def parse_or(self, depth: int) -> Criterion:
        """`or := and ( "||" and )*`, grouped from the left."""
        node = self.parse_and(depth)
        while self.peek_kind() == "OR":
            self.take()
            node = Or(node, self.parse_and(depth))
        return node

    def parse_and(self, depth: int) -> Criterion:
        """`and := not ( "&&" not )*`, grouped from the left."""
        node = self.parse_not(depth)
        while self.peek_kind() == "AND":
            self.take()
            node = And(node, self.parse_not(depth))
        return node

    def parse_not(self, depth: int) -> Criterion:
        """`not := "!" not | primary`."""
        if depth > MAX_NESTING:
            raise ParseError("criterion is nested too deeply")
        if self.peek_kind() == "NOT":
            self.take()
            return Not(self.parse_not(depth + 1))
        return self.parse_primary(depth)

    def parse_primary(self, depth: int) -> Criterion:
        """`primary := "(" criterion ")" | atom`."""
        if self.peek_kind() == "LPAREN":
            self.take()
            node = self.parse_or(depth + 1)
            self.expect("RPAREN")
            return node
        return self.parse_atom()

    def parse_atom(self) -> Criterion:
        """One test: `type = T`, `[field] contains "s"`, or `field <|>|= datetime`."""
        if self.peek_kind() == "CONTAINS":
            self.take()
            needle = self.expect("STRING")[1]
            return Contains(None, needle)
        kind, value = self.take()
        if kind != "IDENT":
            raise ParseError(f"unexpected token: {value!r}")
        field = value.casefold()
        nxt_kind, nxt_val = self.peek()
        if field == "type":
            cmp_kind, op = self.take()
            if cmp_kind != "CMP" or op != "=":
                raise ParseError("type comparison must use =")
            type_token = self.take()
            if type_token[0] != "IDENT":
                raise ParseError("expected a PIR type after type =")
            return TypeIs(type_token[1])
        if nxt_kind == "CONTAINS":
            self.take()
            needle = self.expect("STRING")[1]
            return Contains(field, needle)
        if nxt_kind == "CMP":
            op = self.take()[1]
            instant = self._parse_instant()
            return TimeCompare(field, op, instant)
        raise ParseError(f"unexpected token after {value!r}")

    def _parse_instant(self) -> datetime:
        """The datetime after a comparison operator; a bad value is a ParseError."""
        kind, value = self.take()
        if kind in {"TIME", "IDENT", "STRING"}:
            try:
                return parse_datetime(value)
            except Exception as exc:
                raise ParseError(f"invalid datetime: {value}") from exc
        raise ParseError("expected a datetime")
