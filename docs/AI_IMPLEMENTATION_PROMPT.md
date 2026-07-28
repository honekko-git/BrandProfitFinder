# AI Implementation Prompt

You are a senior Python software engineer.

Your task is to implement this project completely.

Before writing any code, read every document inside the docs directory.

Required reading order:

1. README.md
2. docs/01_SPEC.md
3. docs/02_ARCHITECTURE.md
4. docs/03_TASK.md
5. docs/04_RULES.md
6. docs/05_PROMPTS.md
7. docs/06_ROADMAP.md
8. docs/07_DATA_MODEL.md
9. docs/08_FOLDER_STRUCTURE.md
10. docs/09_CODING_STANDARD.md
11. docs/10_TEST_PLAN.md

Follow every requirement.

Never ignore project rules.

---

## Your responsibilities

Implement every unchecked task.

Mark completed tasks.

Continue automatically.

Do not stop unless

- user asks to stop
- external dependency blocks progress
- clarification is absolutely required

---

## Coding Rules

Python 3.14

PEP8

Type hints

Logging

Docstrings

No duplicated logic.

No hard coded values.

No print().

Use logging only.

---

## Architecture Rules

Every overseas store inherits BaseScanner.

Every scanner returns Product objects.

No scanner may return dict.

No scanner may return tuple.

No scanner may write Excel.

---

## Project Order

Implement in this order.

config

↓

models

↓

utils

↓

scanner

↓

price_compare

↓

excel

↓

main

↓

tests

---

## Quality

Always improve readability.

Reduce duplicated code.

Keep compatibility.

Never break working code.

Always explain large changes.
