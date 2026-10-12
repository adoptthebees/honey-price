"""Tests for scripts/check_docs.py. Run: python3 -m unittest discover -s scripts"""
import http.client
import os
import sys
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_docs as cd  # noqa: E402


def words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(1, n + 1))


def sentences(n: int) -> str:
    return " ".join(f"Sentence {i} here." for i in range(1, n + 1))


class NameRuleTests(unittest.TestCase):
    def test_valid_names(self):
        root = tempfile.mkdtemp()
        for name in ("README.md", "PRICE_UNITS.md"):
            path = os.path.join(root, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("One line.\n")
            self.assertEqual(cd.check_name(path, root), [])

    def test_invalid_names(self):
        root = tempfile.mkdtemp()
        for name in (
            "readme.md",
            "PriceUnits.md",
            "price-units.md",
            "PRICE__UNITS.md",
            "README.MD",
        ):
            path = os.path.join(root, name)
            probs = cd.check_name(path, root)
            self.assertTrue(any(p.rule == "NAME" for p in probs), name)


class DirRuleTests(unittest.TestCase):
    def test_valid_dir_chain(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "DOCS", "SPECS"))
        path = os.path.join(root, "DOCS", "SPECS", "X.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("Text.\n")
        self.assertEqual(cd.check_dir(path, root), [])

    def test_invalid_dir_chain(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "docs", "specs"))
        path = os.path.join(root, "docs", "specs", "X.md")
        probs = cd.check_dir(path, root)
        self.assertTrue(any(p.rule == "DIR" for p in probs))

    def test_github_exempt(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, ".github"))
        path = os.path.join(root, ".github", "NOTE.md")
        self.assertEqual(cd.check_dir(path, root), [])


class SemicolonTests(unittest.TestCase):
    def test_triggers(self):
        probs = cd.check_text("Use a; b.\n", frozenset())
        self.assertTrue(any(p.rule == "SEMICOLON" for p in probs))

    def test_near_miss(self):
        probs = cd.check_text("Use a colon: b.\n", frozenset())
        self.assertFalse(any(p.rule == "SEMICOLON" for p in probs))


class ContractionTests(unittest.TestCase):
    def test_triggers(self):
        probs = cd.check_text("You don't stop.\n", frozenset())
        self.assertTrue(any(p.rule == "CONTRACTION" for p in probs))

    def test_possessive_not_contraction(self):
        probs = cd.check_text("FAO's data is here.\n", frozenset())
        self.assertFalse(any(p.rule == "CONTRACTION" for p in probs))

    def test_quoted_mention_skipped(self):
        probs = cd.check_text('Write "do not" and not "don\'t".\n', frozenset())
        self.assertFalse(any(p.rule == "CONTRACTION" for p in probs))


class AbbreviationTests(unittest.TestCase):
    def test_triggers(self):
        probs = cd.check_text("A fruit, e.g. apple.\n", frozenset())
        self.assertTrue(any(p.rule == "ABBREVIATION" for p in probs))

    def test_near_miss(self):
        probs = cd.check_text("For example use apple.\n", frozenset())
        self.assertFalse(any(p.rule == "ABBREVIATION" for p in probs))

    def test_quoted_mention_skipped(self):
        probs = cd.check_text('Write "for example" and not "e.g.".\n', frozenset())
        self.assertFalse(any(p.rule == "ABBREVIATION" for p in probs))


class WordRuleTests(unittest.TestCase):
    def test_unquoted_ensure(self):
        probs = cd.check_text("We ensure quality.\n", frozenset())
        self.assertTrue(any(p.rule == "WORD" for p in probs))

    def test_quoted_ensure_skipped(self):
        probs = cd.check_text('The word "ensure" is banned.\n', frozenset())
        self.assertFalse(any(p.rule == "WORD" for p in probs))

    def test_may_modal(self):
        probs = cd.check_text("You may open it.\n", frozenset())
        self.assertTrue(any(p.rule == "WORD" and "may" in p.message.lower() for p in probs))

    def test_may_month_near_miss(self):
        probs = cd.check_text("The date is May 2026.\n", frozenset())
        self.assertFalse(any(p.rule == "WORD" for p in probs))

    def test_may_next_to_a_month_in_the_same_paragraph_still_fails(self):
        probs = cd.check_text("You may open it in May 2026.\n", frozenset())
        self.assertTrue(any(p.rule == "WORD" and "may" in p.message.lower() for p in probs))

    def test_month_after_a_day_number_passes(self):
        probs = cd.check_text("The date is 14 May.\n", frozenset())
        self.assertFalse(any(p.rule == "WORD" for p in probs))


class LengthTests(unittest.TestCase):
    def test_instruction_20_passes(self):
        text = "Run " + words(19) + ".\n"
        probs = cd.check_text(text, frozenset())
        self.assertFalse(any(p.rule == "LENGTH" for p in probs))

    def test_instruction_21_fails(self):
        text = "Run " + words(20) + ".\n"
        probs = cd.check_text(text, frozenset())
        self.assertTrue(any(p.rule == "LENGTH" for p in probs))

    def test_description_25_passes(self):
        text = "This text has " + words(22) + ".\n"
        probs = cd.check_text(text, frozenset())
        self.assertFalse(any(p.rule == "LENGTH" for p in probs))

    def test_description_26_fails(self):
        text = "This text has " + words(23) + ".\n"
        probs = cd.check_text(text, frozenset())
        self.assertTrue(any(p.rule == "LENGTH" for p in probs))


class ParagraphTests(unittest.TestCase):
    def test_six_sentences_pass(self):
        probs = cd.check_text(sentences(6) + "\n", frozenset())
        self.assertFalse(any(p.rule == "PARAGRAPH" for p in probs))

    def test_seven_sentences_fail(self):
        probs = cd.check_text(sentences(7) + "\n", frozenset())
        self.assertTrue(any(p.rule == "PARAGRAPH" for p in probs))


class IngTests(unittest.TestCase):
    def test_triggers(self):
        probs = cd.check_text("We are testing now.\n", frozenset())
        self.assertTrue(any(p.rule == "ING" for p in probs))

    def test_allowlist_thing(self):
        probs = cd.check_text("One thing remains.\n", frozenset())
        self.assertFalse(any(p.rule == "ING" for p in probs))

    def test_technical_noun_ing_allowed(self):
        nouns = frozenset({"pricing"})
        probs = cd.check_text("Use pricing data.\n", nouns)
        self.assertFalse(any(p.rule == "ING" for p in probs))


class PassiveTests(unittest.TestCase):
    def test_warning(self):
        probs = cd.check_text("The file is written here.\n", frozenset())
        self.assertTrue(any(p.rule == "PASSIVE" and p.severity == "warning" for p in probs))

    def test_near_miss_active(self):
        probs = cd.check_text("The file sits here.\n", frozenset())
        self.assertFalse(any(p.rule == "PASSIVE" for p in probs))


class ProseSkipTests(unittest.TestCase):
    def test_fenced_code_skipped(self):
        text = "```\ndon't\nensure\n```\nClean line.\n"
        probs = cd.check_text(text, frozenset())
        rules = {p.rule for p in probs}
        self.assertNotIn("CONTRACTION", rules)
        self.assertNotIn("WORD", rules)

    def test_inline_code_skipped_for_word_count(self):
        text = "Run `" + words(30) + "` " + words(5) + ".\n"
        probs = cd.check_text(text, frozenset())
        self.assertFalse(any(p.rule == "LENGTH" for p in probs))


class FindDocumentsTests(unittest.TestCase):
    def test_skips_pycache(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "__pycache__"))
        with open(os.path.join(root, "__pycache__", "X.md"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        with open(os.path.join(root, "OK.md"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        found = cd.find_documents([root], root)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].endswith("OK.md"))


class MainExitTests(unittest.TestCase):
    def test_clean_tree_exit_zero(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "DOCS"))
            path = os.path.join(root, "DOCS", "NOTE.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Short line.\n")
            code = cd.main([root])
            self.assertEqual(code, 0)

    def test_error_exit_one(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "bad.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("ensure\n")
            code = cd.main([path])
            self.assertEqual(code, 1)

    def test_warning_only_exit_zero(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "NOTE.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("The file is written.\n")
            buf = StringIO()
            with redirect_stdout(buf):
                code = cd.main([path])
            self.assertEqual(code, 0)
            self.assertIn("PASSIVE", buf.getvalue())


class HeadingTests(unittest.TestCase):
    def test_heading_word_rules_only(self):
        long = words(30)
        probs = cd.check_text(f"# ensure {long}\n", frozenset())
        self.assertTrue(any(p.rule == "WORD" for p in probs))
        self.assertFalse(any(p.rule == "LENGTH" for p in probs))


# The text of the ASD-STE100 word list, as pdftotext -layout writes it. The first column is 19
# characters wide on the first page and 23 on the second page, as in the real file.
DICTIONARY_SAMPLE = """\
Part 2 - Dictionary: introduction
BE (v),                1. To occur, exist      IF THERE IS
ZZZ (v)                A word in the introduction

Word               Approved meaning/
(part of speech)   ALTERNATIVES                 STE EXAMPLE             Non-STE example
A (art)            Function word:               A FUEL PUMP IS
                   indefinite article           INSTALLED IN
                                                ZONE 10.
abaft (prep)       AFT OF (prep)                THE CONTROL UNIT IS The control unit is
                                                INSTALLED AFT OF    installed abaft the flight
                                                THE FLIGHT          compartment.
abandon (v)        GO (v)                       IF THERE IS A FIRE,     If there is a fire,
                                                IMMEDIATELY GO TO       immediately abandon
                                                A SAFE AREA.            the area.
                   STOP (v)                     IF THE VALUES ARE       If the values are
                                                INCORRECT, STOP         incorrect, abandon the
                                                THE TEST                test procedure.
ABSORB (v),        1.   To take up or into      ABSORB THE FLUID
ABSORBS,                                        WITH A CLEAN CLOTH.
ABSORBED,
ABSORBED


Page 2-1-A2                           Part 2 - Dictionary                          Issue 9
                                                                                2025-01-15
                         ASD-STE100 Simplified Technical English

Word                   Approved meaning/
(part of speech)       ALTERNATIVES              STE EXAMPLE           Non-STE example
BE (v),                1.   To occur, exist      IF THERE IS
IS, WAS,                                         CORROSION ON THE
(also ARE, WERE)                                 PUMP VANES,
                                                 REPLACE THE PUMP.
       No other verb
       forms.
                       2. To have a property,    ACID SOLUTIONS ARE
                          to be equal to         DANGEROUS.
check (v)              MAKE SURE (v)             MAKE SURE THAT IT     Check that it is safe.
CHECK (n)              The procedure you do      DO A CHECK OF THE
                                                 HYDRAULIC SYSTEM.
"""


class DictionaryParseTests(unittest.TestCase):
    def setUp(self):
        self.approved, self.unapproved = cd.parse_dictionary(DICTIONARY_SAMPLE)

    def test_a_word_in_capitals_is_approved_with_each_form_that_its_entry_lists(self):
        for word in ("a", "absorb", "absorbs", "absorbed", "be", "is", "was", "are", "were"):
            self.assertIn(word, self.approved)

    def test_a_word_in_lower_case_is_not_approved_and_has_the_alternatives_of_its_entry(self):
        self.assertEqual(self.unapproved["abaft"], ["aft of"])
        self.assertEqual(self.unapproved["abandon"], ["go", "stop"])

    def test_the_meaning_text_and_the_notes_of_an_entry_are_not_words_of_the_list(self):
        # "To occur" is meaning text in the second column. "No other verb forms" is a note.
        for word in ("to", "occur", "no", "other", "verb", "forms", "been"):
            self.assertNotIn(word, self.approved)

    def test_text_before_the_word_list_is_ignored(self):
        self.assertNotIn("zzz", self.approved)
        self.assertNotIn("zzz", self.unapproved)

    def test_a_word_that_one_entry_approves_is_not_listed_as_unapproved(self):
        self.assertIn("check", self.approved)
        self.assertNotIn("check", self.unapproved)


class VocabularyTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary = cd.Vocabulary(
            approved=frozenset({"use", "the", "data", "value", "make", "sure"}),
            unapproved={"ensure": ["make sure"], "file": ["remove"], "kind": []},
            registry=frozenset({"file", "script", "fao", "time", "series"}),
        )

    def explain(self, word):
        return self.vocabulary.explain(word)

    def test_an_approved_word_passes_in_any_case_and_as_a_plural_or_third_person_form(self):
        for word in ("use", "Use", "values", "uses"):
            self.assertIsNone(self.explain(word), word)

    def test_a_registered_word_passes_with_its_plural(self):
        for word in ("script", "scripts", "series", "FAO", "FAO's"):
            self.assertIsNone(self.explain(word), word)

    def test_a_registered_word_passes_even_when_the_dictionary_does_not_approve_a_verb_of_that_spelling(self):
        self.assertIsNone(self.explain("file"))

    def test_an_unapproved_word_gets_its_approved_alternatives(self):
        self.assertIn("make sure", self.explain("ensure"))
        self.assertIn("not approved", self.explain("kind"))

    def test_a_word_that_is_not_in_the_dictionary_and_not_registered_names_the_remedy(self):
        message = self.explain("gizmo")
        self.assertIn("not in the dictionary", message)
        self.assertIn("AGENTS.md", message)

    def test_a_past_form_of_a_registered_verb_passes(self):
        vocabulary = cd.Vocabulary(frozenset(), {}, frozenset({"download", "store"}))
        for word in ("downloaded", "stored", "downloads"):
            self.assertIsNone(vocabulary.explain(word), word)


class VocabularyInTextTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary = cd.Vocabulary(
            approved=frozenset({"use", "the", "data", "is", "a", "and", "not", "make", "sure", "write"}),
            unapproved={"ensure": ["make sure"]},
            registry=frozenset({"script", "time", "series", "fao"}),
        )

    def vocab_problems(self, text):
        probs = cd.check_text(text, frozenset(), "", vocabulary=self.vocabulary)
        return [p for p in probs if p.rule == "VOCAB"]

    def test_each_word_that_is_not_approved_is_an_error_with_its_line(self):
        probs = self.vocab_problems("Use the data.\n\nUse the gizmo.\n")
        self.assertEqual([(p.line, p.severity) for p in probs], [(3, "error")])
        self.assertIn("gizmo", probs[0].message)

    def test_a_quoted_mention_and_a_code_span_are_not_checked(self):
        self.assertEqual(self.vocab_problems('Write "gizmo" and `gadget`.\n'), [])

    def test_a_hyphenated_word_is_checked_by_its_parts(self):
        self.assertEqual(self.vocab_problems("The time-series data.\n"), [])
        self.assertEqual(len(self.vocab_problems("The time-gizmo data.\n")), 1)

    def test_headings_and_table_cells_are_checked(self):
        self.assertEqual(len(self.vocab_problems("# The gizmo\n")), 1)
        self.assertEqual(len(self.vocab_problems("| Use | gizmo |\n| --- | --- |\n")), 1)

    def test_a_word_with_ing_is_left_to_the_ing_rule(self):
        self.assertEqual(self.vocab_problems("Use the testing data.\n"), [])

    def test_without_a_vocabulary_no_word_is_checked(self):
        probs = cd.check_text("Use the gizmo.\n", frozenset(), "")
        self.assertFalse(any(p.rule == "VOCAB" for p in probs))

    def test_a_file_name_is_not_a_word(self):
        self.assertEqual(self.vocab_problems("# AGENTS.md\n\nUse index.html and data.js.\n"), [])

    def test_a_full_stop_between_sentences_does_not_make_a_file_name(self):
        self.assertEqual(len(self.vocab_problems("Use the data.Gizmo is not data.\n")), 1)


class AgentsTableTests(unittest.TestCase):
    def test_the_checker_enforces_each_word_of_the_table_in_agents_md(self):
        with open(os.path.join(cd.default_repo_root(), "AGENTS.md"), encoding="utf-8") as fh:
            words = [line.split("|")[1].strip().strip('"') for line in fh if line.startswith('| "')]
        self.assertGreater(len(words), 10)
        for word in words:
            self.assertIn(word, cd.DISAPPROVED)


class RegistryTests(unittest.TestCase):
    def test_nouns_and_verbs_come_from_their_own_sections_of_agents_md(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "AGENTS.md"), "w", encoding="utf-8") as fh:
                fh.write("# Title\n\n## Technical nouns\n\n- honey\n- producer price\n\n"
                         "## Technical verbs\n\n- download\n\n## Other\n\n- ignored\n")
            self.assertEqual(cd.load_technical_nouns(root), frozenset({"honey", "producer", "price"}))
            self.assertEqual(cd.load_technical_verbs(root), frozenset({"download"}))

    def test_a_tree_without_agents_md_has_an_empty_registry(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(cd.load_technical_verbs(root), frozenset())


class VocabularyModeTests(unittest.TestCase):
    def run_main(self, text, *argv, dictionary=None):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "NOTE.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            buf = StringIO()
            with redirect_stdout(buf):
                code = cd.main([*argv, path], dictionary=dictionary)
            return code, buf.getvalue()

    def test_the_flag_makes_an_unknown_word_an_error(self):
        code, out = self.run_main("Use the gizmo.\n", "--vocabulary",
                                  dictionary=(frozenset({"use", "the"}), {}))
        self.assertEqual(code, 1)
        self.assertIn("VOCAB", out)

    def test_without_the_flag_the_same_text_passes(self):
        code, _ = self.run_main("Use the gizmo.\n")
        self.assertEqual(code, 0)

    def test_a_dictionary_that_cannot_be_loaded_gives_exit_code_two(self):
        with mock.patch.object(cd, "load_dictionary", side_effect=cd.DictionaryError("no network")):
            code, _ = self.run_main("Use the data.\n", "--vocabulary")
        self.assertEqual(code, 2)

    def test_a_saved_dictionary_is_read_without_a_download(self):
        with tempfile.TemporaryDirectory() as cache:
            with mock.patch.object(cd, "download_pdf", side_effect=AssertionError("must not download")):
                cd.save_dictionary(cache, frozenset({"use"}), {"ensure": ["make sure"]})
                approved, unapproved = cd.load_dictionary(cache)
        self.assertEqual((approved, unapproved), (frozenset({"use"}), {"ensure": ["make sure"]}))


class UnreadableDictionaryTests(unittest.TestCase):
    def run_main(self):
        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "NOTE.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Use the data.\n")
            err = StringIO()
            with redirect_stderr(err), redirect_stdout(StringIO()):
                code = cd.main(["--vocabulary", "--cache", cache, path])
        return code, err.getvalue()

    def test_text_without_the_word_list_header_raises_dictionary_error(self):
        with self.assertRaises(cd.DictionaryError):
            cd.parse_dictionary("garbage\nabaft (prep) aft of\n")

    def test_a_pdf_without_the_word_list_header_gives_exit_code_two(self):
        with mock.patch.object(cd, "download_pdf", return_value="unused.pdf"):
            with mock.patch.object(cd, "pdf_text", return_value="garbage\nabaft (prep) aft of\n"):
                code, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_a_download_cut_off_gives_exit_code_two(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.side_effect = http.client.IncompleteRead(b"part")
        with mock.patch.object(cd.urllib.request, "urlopen", return_value=response):
            with mock.patch.object(cd.time, "sleep"):
                code, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)


class HtmlCommentTests(unittest.TestCase):
    def test_a_multi_line_comment_is_not_checked(self):
        text = "<!--\nThis should be fixed.\n\nIt may fail.\n-->\nThis line is fine.\n"
        self.assertEqual(cd.check_text(text, frozenset()), [])

    def test_text_after_a_multi_line_comment_is_checked_at_its_own_line(self):
        text = "<!--\nThis should be fixed.\n\nIt may fail.\n-->\nThis should fail.\n"
        probs = cd.check_text(text, frozenset())
        self.assertEqual([(p.rule, p.line) for p in probs], [("WORD", 6)])


class QuotedTermTests(unittest.TestCase):
    def test_words_after_a_quote_that_is_a_sentence_fragment_are_checked(self):
        text = 'Use the "file. Then ensure the output; keep it. Say "done".\n'
        probs = cd.check_text(text, frozenset())
        messages = [p.message for p in probs if p.rule == "WORD"]
        self.assertTrue(any("ensure" in m for m in messages), messages)
        self.assertTrue(any(p.rule == "SEMICOLON" for p in probs))

    def test_the_table_row_of_agents_md_passes(self):
        probs = cd.check_text('| "ensure" | "make sure" |\n| --- | --- |\n', frozenset())
        self.assertFalse(any(p.rule == "WORD" for p in probs))

    def test_a_quoted_term_may_contain_a_semicolon(self):
        probs = cd.check_text('The flag says "Missing value; data cannot exist".\n', frozenset())
        self.assertFalse(any(p.rule in ("SEMICOLON", "ING") for p in probs), probs)

    def test_a_quoted_term_may_contain_a_question_mark(self):
        probs = cd.check_text('The panel title is "How reliable is the year?".\n', frozenset())
        self.assertEqual([p for p in probs if p.rule != "PASSIVE"], [])

    def test_a_semicolon_is_reported_when_the_quotes_on_the_line_are_unbalanced(self):
        probs = cd.check_text('Use "a; b" and "c.\n', frozenset())
        self.assertTrue(any(p.rule == "SEMICOLON" for p in probs))


class CurlyApostropheTests(unittest.TestCase):
    def test_a_contraction_with_an_ascii_or_curly_apostrophe_triggers(self):
        for text in ("It isn't here.\n", "It isn\u2019t here.\n"):
            probs = cd.check_text(text, frozenset())
            self.assertTrue(any(p.rule == "CONTRACTION" for p in probs), text)


class SentenceSplitTests(unittest.TestCase):
    def test_a_full_stop_after_an_abbreviation_does_not_end_a_sentence(self):
        for text in (
            "Send it to the U.S. Office now.",
            "Use a fruit, e.g. The apple.",
            "Use a fruit, i.e. The apple.",
            "Ask Dr. Smith now.",
            "Ask Mr. Smith now.",
            "Ask Mrs. Smith now.",
            "Ask Ms. Smith now.",
            "Use item No. Two now.",
            "See Fig. Two now.",
            "Use a rule, etc. The end.",
        ):
            self.assertEqual(len(cd.split_sentences(text)), 1, text)

    def test_a_single_capital_letter_ends_a_sentence(self):
        self.assertEqual(len(cd.split_sentences("The value is divided by K. The neighbors differ.")), 2)

    def test_a_decimal_number_does_not_end_a_sentence(self):
        self.assertEqual(len(cd.split_sentences("The value is 1.645 for each file.")), 1)

    def test_a_full_stop_before_a_capital_still_ends_a_sentence(self):
        self.assertEqual(len(cd.split_sentences("Use the file. Then keep it.")), 2)

    def test_a_sentence_with_an_abbreviation_is_one_sentence_and_too_long(self):
        text = ("Send each file to the U.S. Office for review and then keep the copy in the shared "
                "folder until the end of the month when the next report is due.\n")
        self.assertEqual(len(cd.split_sentences(text.strip())), 1)
        probs = cd.check_text(text, frozenset())
        self.assertTrue(any(p.rule == "LENGTH" for p in probs))


class InstructionTests(unittest.TestCase):
    def test_an_instruction_that_starts_with_include_has_the_20_word_limit(self):
        probs = cd.check_text("Include " + words(22) + ".\n", frozenset())
        self.assertTrue(any(p.rule == "LENGTH" for p in probs))

    def test_an_instruction_of_20_words_that_starts_with_include_passes(self):
        probs = cd.check_text("Include " + words(19) + ".\n", frozenset())
        self.assertFalse(any(p.rule == "LENGTH" for p in probs))

    def test_note_is_not_an_instruction(self):
        probs = cd.check_text("Note that " + words(23) + ".\n", frozenset())
        self.assertFalse(any(p.rule == "LENGTH" for p in probs))
        self.assertFalse(cd.is_instruction("Note that the file is here."))


class HyphenatedWordTests(unittest.TestCase):
    def test_a_disapproved_part_of_a_hyphenated_word_is_reported(self):
        probs = cd.check_text("Use the per-pound price.\n", frozenset())
        self.assertTrue(any(p.rule == "WORD" and "per" in p.message for p in probs))

    def test_a_word_in_backticks_is_not_checked(self):
        probs = cd.check_text("Run `check_docs` now.\n", frozenset())
        self.assertFalse(any(p.rule == "WORD" for p in probs))

    def test_the_same_word_outside_backticks_is_checked(self):
        probs = cd.check_text("Run check_docs now.\n", frozenset())
        self.assertTrue(any(p.rule == "WORD" for p in probs))




if __name__ == "__main__":
    unittest.main()
