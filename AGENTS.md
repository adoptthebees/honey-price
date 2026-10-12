# AGENTS.md

This file gives instructions to AI tools. Read this file before you start a task.

## Tool

The tool in this directory is for data about honey. These data include:

- The producer price of honey for each pound (lb).
- The export price of honey for each pound (lb).
- The annual production of honey in all countries.

Open `index.html` in a browser to use the tool. To make `data/honey_data.js` again, use `python3 scripts/build_data.py`.

A GitHub workflow examines the FAOSTAT files each week. It makes the data file again when FAOSTAT has newer files. It also saves the status date. To do the tests, use `python3 -m unittest discover -s scripts`. The directory `DOCS/SPECS` has the specifications of the tool.

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

- Use only the approved words in the dictionary. Use a word that is not in the dictionary only as a technical noun or verb (Rule 1.1).
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

The dictionary has these words as not approved. Replace each word as follows:

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

These words are technical nouns for the data:

- export value
- export quantity
- import quantity
- retail price
- wholesale price
- customs average
- kilogram
- tonne
- kg
- lb
- MB
- US dollar
- tonnage
- grade
- trade
- element
- series
- series break
- flag
- official value
- estimated value
- imputed value
- external value
- non-official value
- World total
- World row
- bee
- year
- month
- week
- day
- Monday
- two
- minute
- second
- pixel
- cent
- public domain

These words are technical nouns for the statistics:

- statistics
- average
- confidence score
- confidence interval
- scale
- series scale
- pooled scale
- half width
- neighbor
- miss
- spread
- median
- mean
- percentile
- logarithm
- natural logarithm
- exponential
- square root
- square
- multiplier
- class multiplier
- estimate multiplier
- penalty
- rounding
- age
- share
- ratio
- normal curve
- tail
- parity
- assumption
- probability
- revision
- decimal
- digit
- whole number
- zero
- percent
- jump
- history
- gap

These words are technical nouns for the software:

- software
- computer
- script
- data file
- file
- directory
- repository
- workflow
- database
- memory
- page
- browser
- server
- site
- cache
- command
- option
- request
- endpoint
- route
- parameter
- client
- response
- publication
- package
- framework
- loader
- adapter
- program
- router
- frontend
- separator
- summary
- permission
- branch
- commit
- tab
- message
- address
- button
- panel
- mouse
- label
- runner
- dump
- secret
- variable
- fixture
- link
- key
- list
- string
- array
- null
- zip
- byte
- schedule
- format
- version
- slider
- field
- content
- style
- failure
- warning
- switch
- column
- axis
- circle
- diamond
- triangle
- band
- bar
- chart
- table
- status
- JSON
- CSV
- HTML
- CSS
- JavaScript
- Markdown
- MD5
- UTC
- AI

These words are technical nouns for the documents:

- document
- context document
- specification
- plan
- reference
- term
- purpose
- title
- heading
- section
- text
- letter
- word
- sentence
- paragraph
- rule
- dictionary
- noun
- defect
- verb
- topic
- semicolon
- imperative
- path
- note
- license
- issue

These words are technical nouns for the market data system:

- API
- CDN
- application
- backend
- build
- deal
- duplicate
- attribute
- filter
- forecast
- GB
- hash
- header
- index
- KB
- line
- manifest
- market
- marketplace
- product owner
- mirror
- ms
- parser
- PDF
- query
- quote
- response
- role
- schema
- state
- transaction
- visitor
- dataset
- dependency
- migration
- partner
- reader
- reporter
- region
- rollback
- SQL
- statement
- unique index
- variety
- certification

These words are technical nouns for the trade data:

- beeswax
- case
- colony
- CIF
- duty
- exporter
- freight
- HTS
- importer
- insurance
- municipality
- notice
- origin
- port
- remedy
- tariff
- stock
- yield
- air
- vessel

These words are names:

- FAO
- FAOSTAT
- USDA
- UNSD
- Eurostat
- OWID
- GitHub
- Git
- Internet Archive
- PostgreSQL
- SQLite
- China
- Romania
- STE
- Simplified Technical English
- Food and Agriculture Organization of the United Nations
- Exchange Honey
- Federal Register
- AMS
- NASS
- ESMIS
- March
- December
- ERS
- IBGE
- USITC
- Census
- Brazil

Add each new technical noun to this list.

## Technical verbs

STE lets you use a technical verb that is not in the dictionary (Rule 1.12). These words are technical verbs for the tool:

- download
- install
- save
- store
- sort
- update
- filter

Add each new technical verb to this list.

## Context documents

A context document is a document that gives instructions or facts to an AI tool. For example, `AGENTS.md` and `CLAUDE.md` are context documents. Each context document obeys the rules in this file.

The script `scripts/check_docs.py` examines each Markdown file in the repository. Thus it examines the context documents too.

## Examine the documents

Use `python3 scripts/check_docs.py` to examine the documents. The script examines the names, the length of the sentences and the paragraphs, and the words in the table above. It gives the exit code 1 when a document has an error.

Add the option `--vocabulary` to examine each word against the dictionary. The script downloads the specification one time and keeps the word list in the temporary directory. This option uses the command `pdftotext`. The script gives the exit code 2 when it cannot read the dictionary.

The script examines only files that have `.md` at the end of the name. It does not examine how you use a word. Use each word only as the dictionary gives it (Rules 1.2 and 1.3).

The workflow `Checks` starts the script with the option `--vocabulary` on each push to the branch `main` and on each pull request.

## Complete a task

Before you complete a task, examine each document that you write or change. Use `python3 scripts/check_docs.py --vocabulary` for this. Make sure that the script gives no error and no warning. Make sure that each document obeys this file.
