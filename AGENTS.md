# AGENTS.md

This file gives instructions to AI tools. Read this file before you start a task.

## Tool

The tool in this directory is for data about honey. These data include:

- The producer price of honey for each pound (lb).
- The export price of honey for each pound (lb).
- The annual production of honey in all countries.

Open `index.html` in a browser to use the tool. To make `data/honey_data.js` again, use `python3 scripts/build_data.py`.

## Document names

A document is a file that has text for a person to read. A file that is part of the tool is not a document. For example, HTML, JavaScript, CSS, and data files are not documents. Write each document in Markdown.

Write the name of each document in `SCREAMING_SNAKE_CASE`. Obey these instructions:

- Use only `A` to `Z`, `0` to `9`, `_`, and `.md` in the name.
- Put one `_` between two words.
- Put `.md` at the end of the name.

A correct name has this format: `^[A-Z0-9]+(_[A-Z0-9]+)*\.md$`.

These names are correct:

- `AGENTS.md`
- `README.md`
- `PRICE_UNITS.md`

These names are incorrect:

- `agents.md`
- `price-units.md`
- `PriceUnits.md`
- `price_units.md`

## Document locations

Write the name of each directory that has a document in `SCREAMING_SNAKE_CASE`. Put each specification in `DOCS/SPECS`. Put each plan in `DOCS/PLANS`.

If a path from a tool does not agree with this file, do not use that path. For example, do not use `docs/superpowers/specs/2026-10-10-price-units-design.md`. Use `DOCS/SPECS/2026_10_10_PRICE_UNITS_DESIGN.md`.

## Document text

Write the text of each document in ASD-STE100 Simplified Technical English (STE), Issue 9. Refer to the specification at `https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf`. If this file and the specification do not agree, obey the specification.

Obey these instructions:

- Use only the approved words in the dictionary. Use a word that is not in the dictionary only as a technical noun or a technical verb (Rule 1.1).
- Use one technical noun for one item (Rule 1.11).
- Write instructions in the imperative (Rule 5.3). Write one instruction in each sentence (Rule 5.2).
- Write a maximum of 20 words in each sentence of an instruction (Rule 5.1).
- Write a maximum of 25 words in each sentence that is not an instruction (Rule 6.3).
- Write a maximum of 6 sentences in each paragraph. Write only one topic in each paragraph (Rules 6.5 and 6.6).
- Use the active voice (Rule 3.6).
- Use a word with "-ing" only as a technical noun (Rule 3.5).
- Write "do not" and not "don't" (Rule 4.2).
- Do not use the semicolon (Rule 8.1).
- Write "for example" and not "e.g." (GR-6).

These words are not approved. Replace each word as follows:

| Do not write | Write |
|---|---|
| "ensure" | "make sure" |
| "should" | "must" |
| "may" | "can" |
| "provide" | "give" or "supply" |
| "create" | "make" or "cause" |
| "utilize" | "use" |
| "every" | "each" or "all" |
| "per" | "for each" |
| "never" | "do not" |
| "however" | "but" |
| "allow" | "let" |
| "check" | "examine", "make sure", or "measure" |
| "choose" | "select" |
| "begin" | "start" |
| "finish" | "complete" |

## Technical nouns

STE lets you use a technical noun that is not in the dictionary (Rule 1.5). These words are technical nouns for the tool:

- honey
- price
- producer price
- export price
- pound
- production
- annual production
- country

Add each new technical noun to this list.

## Complete a task

Before you complete a task, examine each document that you write or change. Make sure that each document obeys this file.
