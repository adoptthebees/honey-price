"""Check project Markdown documents against ASD-STE100 rules.

    python3 scripts/check_docs.py [--vocabulary] [--cache DIR] [PATH ...]

The default run checks the rules that need no dictionary: file and directory names, sentence
length, paragraph length, the words that AGENTS.md lists as not approved, and so on.
With --vocabulary the script also checks each word against the ASD-STE100 dictionary. It
downloads the specification from asd-ste100.org once, reads the word list with pdftotext and keeps
the list in the cache directory. It does not keep the specification in the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Sequence

SKIP_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", ".venv"})
NAME_RE = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*\.md$")
DIR_RE = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")
DIR_EXEMPT = frozenset({".github"})

WORD_TOKEN = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*|CODE|URL")
SENTENCE_END = re.compile(r'[.!?](?=\s+(?:[A-Z0-9"\u201c]|CODE))')
# A file name such as AGENTS.md or index.html is a name, not a word.
FILE_EXTENSIONS = "md|py|js|css|html|yml|yaml|json|txt|zip|csv|pdf"
WORD_RE = re.compile(rf"[A-Za-z0-9_]+\.(?:{FILE_EXTENSIONS})\b|[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")

IMPERATIVE_VERBS = frozenset({
    "open", "run", "write", "use", "put", "make", "add", "read", "set", "install",
    "push", "commit", "copy", "examine", "refer", "obey", "replace", "select",
    "start", "complete", "stop", "remove", "keep", "send", "save", "find", "go",
    "click", "press", "type", "enter", "change", "edit", "delete", "update",
    "build", "test", "close", "give", "supply", "measure", "apply", "ask",
    "compare", "connect", "define", "download", "get", "hold", "identify", "let",
    "list", "load", "mark", "move", "name", "note", "pull", "record", "reload",
    "rename", "repeat", "report", "return", "review", "rewrite", "show", "split",
    "take", "tell", "try", "turn", "upload", "view", "wait", "work", "do",
})

ING_ALLOW = frozenset({
    "thing", "things", "nothing", "something", "anything", "everything", "during",
    "bring", "brings", "string", "strings", "ring", "rings", "spring", "king",
    "wing", "sing", "swing", "ceiling", "morning", "evening", "ping",
})

DISAPPROVED: dict[str, str] = {}
for _w, _repl in (
    ("ensure", "make sure"), ("ensures", "make sure"), ("ensured", "make sure"),
    ("ensuring", "make sure"),
    ("should", "must"),
    ("may", "can"),
    ("provide", "give or supply"), ("provides", "give or supply"),
    ("provided", "give or supply"), ("providing", "give or supply"),
    ("create", "make or cause"), ("creates", "make or cause"),
    ("created", "make or cause"), ("creating", "make or cause"),
    ("utilize", "use"), ("utilizes", "use"), ("utilized", "use"),
    ("utilizing", "use"), ("utilise", "use"), ("utilises", "use"),
    ("utilised", "use"), ("utilising", "use"),
    ("every", "each or all"),
    ("per", "for each"),
    ("never", "do not"),
    ("however", "but"),
    ("allow", "let"), ("allows", "let"), ("allowed", "let"), ("allowing", "let"),
    ("check", "examine, make sure, or measure"), ("checks", "examine, make sure, or measure"),
    ("checked", "examine, make sure, or measure"), ("checking", "examine, make sure, or measure"),
    ("choose", "select"), ("chooses", "select"), ("chose", "select"),
    ("chosen", "select"), ("choosing", "select"),
    ("begin", "start"), ("begins", "start"), ("began", "start"), ("begun", "start"),
    ("beginning", "start"),
    ("finish", "complete"), ("finishes", "complete"), ("finished", "complete"),
    ("finishing", "complete"),
):
    DISAPPROVED[_w] = _repl

CONTRACTION_RE = re.compile(
    r"\w+n't|\w+['\u2019](?:ll|re|ve|d|m)\b|"
    r"\b(?:it|that|there|what|here|let|he|she|who)['\u2019]s\b",
    re.IGNORECASE,
)
ABBREV_RE = re.compile(r"e\.g\.|i\.e\.|etc\.|(?<![A-Za-z])etc(?![A-Za-z])", re.IGNORECASE)
BE_FORMS = frozenset({"is", "are", "was", "were", "be", "been", "being"})
PASSIVE_PARTS = frozenset({
    "made", "given", "written", "shown", "known", "done", "seen", "taken",
    "kept", "found", "built", "sent", "held", "chosen", "broken",
})
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
INLINE_CODE_RE = re.compile(r"`[^`]+`")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
HEADING_RE = re.compile(r"^(#+)\s*(.*)")
TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)")


@dataclass(frozen=True)
class Problem:
    path: str
    line: int
    rule: str
    message: str
    severity: str  # "error" or "warning"


def default_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_section(root: str, heading: str) -> frozenset[str]:
    """The words of the bullet items under one "## heading" of AGENTS.md."""
    agents = os.path.join(root, "AGENTS.md")
    if not os.path.isfile(agents):
        return frozenset()
    words: set[str] = set()
    in_section = False
    with open(agents, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("## "):
                in_section = line == heading
                continue
            if in_section and line.startswith("- "):
                words.update(line[2:].strip().lower().split())
    return frozenset(words)


def load_technical_nouns(root: str) -> frozenset[str]:
    return _load_section(root, "## Technical nouns")


def load_technical_verbs(root: str) -> frozenset[str]:
    return _load_section(root, "## Technical verbs")


# ---- The ASD-STE100 dictionary ---------------------------------------------------------------
PDF_URL = "https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf"
PDF_NAME = "ASD-STE100_ISSUE9.pdf"
DICTIONARY_NAME = "ste_dictionary.json"
DEFAULT_CACHE = os.path.join(tempfile.gettempdir(), "honey_price_cache")

POS_TAG_RE = re.compile(r"\((?:v|n|adj|adv|prep|art|con|conj|pron|TN|TV|abbr)\)", re.IGNORECASE)
LIST_HEADER_RE = re.compile(r"^Word\s+Approved")
LIST_SKIP_RE = re.compile(r"^(Issue 9|Page \d|\d{4}-\d{2}-\d{2}|\s*ASD[- ]STE100|\s*Blank Page)")
LIST_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
ALTERNATIVE_RE = re.compile(r"[A-Z][A-Z'-]*(?: [A-Z][A-Z'-]*)*")


class DictionaryError(Exception):
    """The dictionary cannot be read."""


def _is_capital(word: str) -> bool:
    return word.isupper() and (len(word) > 1 or word in ("A", "I"))


def parse_dictionary(text: str) -> tuple[frozenset[str], dict[str, list[str]]]:
    """Read the word list of the specification, as pdftotext -layout writes it.

    The first column holds the word. An approved word and each of its forms are in capital
    letters. A word that is not approved is in lower case, and the second column gives the
    approved alternatives. The width of the first column changes from page to page, so the
    header of each page gives the start of the second column.
    """
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith("abaft (prep)")), None)
    if first is None:
        raise DictionaryError("the word list does not start with the entry abaft")
    start = max(i for i in range(first) if LIST_HEADER_RE.match(lines[i]))
    approved: set[str] = set()
    unapproved: dict[str, list[str]] = {}
    second, third, current = 19, 48, None   # the columns, and the entry that the lines belong to
    for line in lines[start:]:
        if LIST_HEADER_RE.match(line):
            second = line.index("Approved")
            continue
        if "STE EXAMPLE" in line:
            third = line.index("STE EXAMPLE")
            continue
        if LIST_SKIP_RE.match(line) or not line.strip():
            continue
        alternatives = line[second:third]
        if not line[:second].strip():
            if current in unapproved and POS_TAG_RE.search(alternatives):
                unapproved[current].extend(_alternatives(alternatives, unapproved[current]))
            continue
        first_column = line[:second]
        words = LIST_WORD_RE.findall(POS_TAG_RE.sub(" ", first_column))
        if not words:
            continue
        if POS_TAG_RE.search(first_column):
            head = [w for w in words if w != "also"]
            if head and all(_is_capital(w) or w == "also" for w in words):
                approved.update(w.lower() for w in words if _is_capital(w))
                current = None
            else:
                current = " ".join(w.lower() for w in head)
                unapproved.setdefault(current, [])
                unapproved[current].extend(_alternatives(alternatives, unapproved[current]))
        elif current is None:
            approved.update(w.lower() for w in words if _is_capital(w))   # the forms of an approved word
    for word in approved:
        unapproved.pop(word, None)
    return frozenset(approved), unapproved


def _alternatives(segment: str, known: list[str]) -> list[str]:
    found = ALTERNATIVE_RE.findall(POS_TAG_RE.sub("|", segment).replace("|", " | "))
    return [a.lower() for a in found if a.lower() not in known and a != "TN"]


def download_pdf(cache_dir: str) -> str:
    """Return the path of the specification in the cache. Download it when it is not there."""
    path = os.path.join(cache_dir, PDF_NAME)
    if os.path.exists(path):
        return path
    os.makedirs(cache_dir, exist_ok=True)
    error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(PDF_URL, timeout=120) as response, open(path + ".part", "wb") as out:
                shutil.copyfileobj(response, out)
            os.replace(path + ".part", path)
            return path
        except OSError as exc:      # URLError is an OSError
            error = exc
            time.sleep(2 * (attempt + 1))
    raise DictionaryError(f"cannot download {PDF_URL}: {error}")


def pdf_text(pdf_path: str) -> str:
    try:
        done = subprocess.run(["pdftotext", "-layout", pdf_path, "-"], capture_output=True,
                              text=True, check=True, timeout=180)
    except FileNotFoundError:
        raise DictionaryError("pdftotext is not installed (package poppler-utils)") from None
    except subprocess.SubprocessError as exc:
        raise DictionaryError(f"pdftotext failed: {exc}") from None
    return done.stdout


def save_dictionary(cache_dir: str, approved: Iterable[str], unapproved: dict[str, list[str]]) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, DICTIONARY_NAME), "w", encoding="utf-8") as out:
        json.dump({"source": PDF_URL, "approved": sorted(approved), "unapproved": unapproved}, out)


def load_dictionary(cache_dir: str = DEFAULT_CACHE) -> tuple[frozenset[str], dict[str, list[str]]]:
    """The approved words and the words that are not approved, from the cache or the specification."""
    saved = os.path.join(cache_dir, DICTIONARY_NAME)
    if os.path.exists(saved):
        try:
            with open(saved, encoding="utf-8") as fh:
                data = json.load(fh)
            return frozenset(data["approved"]), data["unapproved"]
        except (ValueError, KeyError):
            pass    # a cut-off file: read the specification again
    approved, unapproved = parse_dictionary(pdf_text(download_pdf(cache_dir)))
    if len(approved) < 800 or len(unapproved) < 800:
        raise DictionaryError(f"the word list looks incomplete: {len(approved)} approved words, "
                              f"{len(unapproved)} words that are not approved")
    save_dictionary(cache_dir, approved, unapproved)
    return approved, unapproved


class Vocabulary:
    """Decide whether a word is allowed: approved, or a technical noun or verb of AGENTS.md."""

    def __init__(self, approved: Iterable[str], unapproved: dict[str, list[str]], registry: Iterable[str]):
        self.approved = frozenset(approved)
        self.unapproved = unapproved
        self.registry = frozenset(registry)

    @staticmethod
    def _bases(word: str) -> Iterable[str]:
        """The word, and the word without a regular ending: plural, third person, past form."""
        yield word
        if word.endswith("ies") and len(word) > 4:
            yield word[:-3] + "y"
        for suffix in ("es", "s", "ed", "d"):
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                yield word[:-len(suffix)]

    def explain(self, word: str) -> str | None:
        """None when the word is allowed, else the reason."""
        low = word.lower().replace("\u2019", "'")
        if low.endswith("'s"):
            low = low[:-2]
        if low in self.registry or low in self.approved:
            return None
        for part in low.split("-") if "-" in low else [low]:
            bases = list(self._bases(part))
            if any(b in self.approved or b in self.registry for b in bases):
                continue
            for b in bases:
                if b in self.unapproved:
                    alternatives = ", ".join(self.unapproved[b][:3])
                    return f"{part} is not approved" + (f": use {alternatives}" if alternatives else "")
            return (f"{part} is not in the dictionary: use an approved word, "
                    "or add it to Technical nouns or Technical verbs in AGENTS.md")
        return None


def find_documents(paths: Sequence[str] | None = None, root: str | None = None) -> list[str]:
    if root is None:
        root = default_repo_root()
    if not paths:
        paths = [root]
    found: list[str] = []
    for p in paths:
        ap = os.path.abspath(p)
        if os.path.isfile(ap):
            if ap.lower().endswith(".md"):
                found.append(ap)
            continue
        if not os.path.isdir(ap):
            continue
        for dirpath, dirnames, filenames in os.walk(ap):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for name in filenames:
                if name.lower().endswith(".md"):
                    found.append(os.path.join(dirpath, name))
    return sorted(set(found))


def _rel_path(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, os.getcwd())
    except ValueError:
        return path


def _is_under_root(path: str, root: str) -> bool:
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    try:
        os.path.relpath(path, root)
    except ValueError:
        return False
    return path == root or path.startswith(root + os.sep)


def check_name(path: str, root: str) -> list[Problem]:
    rel = _display_path(path, root)
    base = os.path.basename(path)
    if NAME_RE.match(base):
        return []
    return [Problem(rel, 0, "NAME", f"file name must match {NAME_RE.pattern}", "error")]


def check_dir(path: str, root: str) -> list[Problem]:
    if not _is_under_root(path, root):
        return []
    rel = _display_path(path, root)
    parts = os.path.relpath(path, root).split(os.sep)[:-1]
    out: list[Problem] = []
    for part in parts:
        if part in DIR_EXEMPT:
            continue
        if DIR_RE.match(part):
            continue
        out.append(Problem(rel, 0, "DIR", f"directory name must match {DIR_RE.pattern}", "error"))
    return out


def _display_path(path: str, root: str) -> str:
    try:
        return os.path.relpath(os.path.abspath(path), os.getcwd())
    except ValueError:
        return path


def normalize_prose_line(line: str) -> str:
    line = HTML_COMMENT_RE.sub("", line)
    line = HTML_TAG_RE.sub("", line)
    line = INLINE_CODE_RE.sub("CODE", line)
    line = URL_RE.sub("URL", line)
    line = LINK_RE.sub(lambda m: m.group(1), line)
    return line


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    protected = text
    for m in re.finditer(r"\d+\.\d+|[\w.-]+\.\w{2,}", protected):
        segment = m.group(0)
        if "." in segment and not segment.endswith("."):
            token = segment.replace(".", "\u0001")
            protected = protected.replace(segment, token, 1)
    parts: list[str] = []
    start = 0
    for m in SENTENCE_END.finditer(protected):
        end = m.start() + 1
        parts.append(protected[start:end].replace("\u0001", "."))
        start = m.end()
    tail = protected[start:].replace("\u0001", ".")
    if tail.strip():
        parts.append(tail)
    return parts if parts else [text]


def count_words(text: str) -> int:
    return len(WORD_TOKEN.findall(text))


def is_instruction(sentence: str) -> bool:
    s = sentence.strip()
    low = s.lower()
    if low.startswith("do not "):
        return True
    words = WORD_TOKEN.findall(s)
    if not words:
        return False
    first = words[0].lower()
    return first in IMPERATIVE_VERBS


def iter_quoted_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(text):
        if text[i] in ('"', '\u201c'):
            close = '"' if text[i] == '"' else '\u201d'
            j = i + 1
            while j < len(text) and text[j] != close:
                j += 1
            if j < len(text):
                spans.append((i, j + 1))
                i = j + 1
                continue
        i += 1
    return spans


def in_span(pos: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def next_to_number(text: str, match: re.Match) -> bool:
    """True when a number comes directly before or after the match, as in 14 May or May 2026."""
    return bool(re.match(r"\s+\d", text[match.end():]) or re.search(r"\d\s+$", text[:match.start()]))


def check_word_level(
    text: str,
    line: int,
    path: str,
    ing_allow: frozenset[str],
    vocabulary: Vocabulary | None = None,
) -> list[Problem]:
    out: list[Problem] = []
    quoted = iter_quoted_spans(text)
    if any(not in_span(m.start(), quoted) for m in re.finditer(";", text)):
        out.append(Problem(path, line, "SEMICOLON", "do not use a semicolon", "error"))
    for m in CONTRACTION_RE.finditer(text):
        if not in_span(m.start(), quoted):
            out.append(Problem(path, line, "CONTRACTION", f"do not use contraction {m.group(0)}", "error"))
    for m in ABBREV_RE.finditer(text):
        if not in_span(m.start(), quoted):
            out.append(Problem(path, line, "ABBREVIATION", f"do not use abbreviation {m.group(0)}", "error"))
    reported: set[str] = set()      # one VOCAB error for each word on a line
    for m in WORD_RE.finditer(text):
        word = m.group(0)
        low = word.lower()
        if in_span(m.start(), quoted) or "." in word:
            continue
        if low in DISAPPROVED:
            if low == "may" and word[0].isupper() and next_to_number(text, m):
                continue
            out.append(Problem(path, line, "WORD", f"use {DISAPPROVED[low]} instead of {word}", "error"))
            continue
        is_ing = len(low) >= 4 and low.endswith("ing")
        if vocabulary and not is_ing and len(low) > 1 and not any(c.isdigit() for c in low) and word not in ("CODE", "URL"):
            reason = vocabulary.explain(word)
            if reason and low not in reported:
                reported.add(low)
                out.append(Problem(path, line, "VOCAB", reason, "error"))
        if is_ing:
            if low in ING_ALLOW or low in ing_allow:
                continue
            out.append(Problem(path, line, "ING", f"do not use -ing word {word}", "error"))
    tokens = WORD_TOKEN.findall(text)
    for i, tok in enumerate(tokens):
        low = tok.lower()
        if low not in BE_FORMS or i + 1 >= len(tokens):
            continue
        nxt = tokens[i + 1].lower()
        past = nxt in PASSIVE_PARTS or (len(nxt) > 3 and nxt.endswith("ed"))
        if not past and i + 2 < len(tokens):
            nxt2 = tokens[i + 2].lower()
            past = nxt2 in PASSIVE_PARTS or (len(nxt2) > 3 and nxt2.endswith("ed"))
        if past:
            out.append(Problem(path, line, "PASSIVE", "possible passive voice", "warning"))
    return out


def check_length_and_paragraph(
    unit: str,
    start_line: int,
    path: str,
) -> list[Problem]:
    out: list[Problem] = []
    sentences = split_sentences(unit)
    if len(sentences) > 6:
        out.append(Problem(path, start_line, "PARAGRAPH", "more than 6 sentences", "error"))
    for sent in sentences:
        wc = count_words(sent)
        limit = 20 if is_instruction(sent) else 25
        if wc > limit:
            out.append(
                Problem(
                    path,
                    start_line,
                    "LENGTH",
                    f"sentence has {wc} words; limit is {limit}",
                    "error",
                )
            )
    return out


def check_text(text: str, technical_nouns: frozenset[str] | None = None, path: str = "",
               vocabulary: Vocabulary | None = None) -> list[Problem]:
    ing_allow = ING_ALLOW | (technical_nouns or frozenset())
    lines = text.splitlines()
    out: list[Problem] = []
    in_fence = False
    fence_mark = ""
    i = 0
    while i < len(lines):
        raw = lines[i]
        if FENCE_RE.match(raw):
            mark = FENCE_RE.match(raw).group(1)
            if not in_fence:
                in_fence = True
                fence_mark = mark
            elif raw.strip().startswith(fence_mark):
                in_fence = False
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        lineno = i + 1
        hm = HEADING_RE.match(raw)
        if hm:
            body = normalize_prose_line(hm.group(2))
            out.extend(check_word_level(body, lineno, path, ing_allow, vocabulary))
            i += 1
            continue
        if raw.strip().startswith("|"):
            if TABLE_SEP_RE.match(raw):
                i += 1
                continue
            body = normalize_prose_line(raw)
            out.extend(check_word_level(body, lineno, path, ing_allow, vocabulary))
            i += 1
            continue
        lm = LIST_RE.match(raw)
        if lm:
            start = i
            parts = [lm.group(3)]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    break
                if FENCE_RE.match(nxt) or HEADING_RE.match(nxt) or LIST_RE.match(nxt):
                    break
                if nxt.startswith((" ", "\t")):
                    parts.append(nxt.strip())
                    i += 1
                    continue
                break
            unit = normalize_prose_line(" ".join(parts))
            out.extend(check_word_level(unit, start + 1, path, ing_allow, vocabulary))
            out.extend(check_length_and_paragraph(unit, start + 1, path))
            continue
        if not raw.strip():
            i += 1
            continue
        start = i
        parts = [raw]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                break
            if FENCE_RE.match(nxt) or HEADING_RE.match(nxt) or LIST_RE.match(nxt):
                break
            if nxt.strip().startswith("|"):
                break
            parts.append(nxt)
            i += 1
        unit = normalize_prose_line(" ".join(parts))
        out.extend(check_word_level(unit, start + 1, path, ing_allow, vocabulary))
        out.extend(check_length_and_paragraph(unit, start + 1, path))
    return out


def check_file(path: str, root: str, technical_nouns: frozenset[str] | None = None,
               vocabulary: Vocabulary | None = None) -> list[Problem]:
    disp = _display_path(path, root)
    nouns = technical_nouns if technical_nouns is not None else load_technical_nouns(root)
    out = check_name(path, root) + check_dir(path, root)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        out.append(Problem(disp, 0, "READ", str(exc), "error"))
        return out
    out.extend(check_text(text, nouns, disp, vocabulary))
    return out


def format_problem(prob: Problem) -> str:
    line = prob.line if prob.line > 0 else 1
    return f"{prob.path}:{line}: {prob.rule}: {prob.message}"


def main(argv: Sequence[str] | None = None,
         dictionary: tuple[Iterable[str], dict[str, list[str]]] | None = None) -> int:
    """Check the documents. `dictionary` lets a test give the word list instead of the PDF."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="*", help="files or directories; default: the repository")
    parser.add_argument("--vocabulary", action="store_true",
                        help="also check each word against the ASD-STE100 dictionary")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="directory for the downloaded specification")
    args = parser.parse_args(argv)
    root = default_repo_root()
    nouns = load_technical_nouns(root)
    vocabulary = None
    if args.vocabulary:
        try:
            approved, unapproved = dictionary if dictionary is not None else load_dictionary(args.cache)
        except DictionaryError as exc:
            print(f"cannot read the ASD-STE100 dictionary: {exc}", file=sys.stderr)
            return 2
        vocabulary = Vocabulary(approved, unapproved, nouns | load_technical_verbs(root))
    problems: list[Problem] = []
    for doc in find_documents(args.paths or [root], root):
        problems.extend(check_file(doc, root, nouns, vocabulary))
    errors = warnings = 0
    for prob in problems:
        print(format_problem(prob))
        if prob.severity == "error":
            errors += 1
        else:
            warnings += 1
    print(f"errors: {errors}, warnings: {warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
