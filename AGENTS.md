# AGENTS.md

Rules for coding agents and people working on shadecast. The project turns any city into an urban heat decision
problem from open, credential-free data: given a budget, which cooling measures should a city build, and where.
The design, its sections and every work item live in GitHub issues, starting at
[issue #18](https://github.com/deepsaia/shadecast/issues/18). Nothing about design or planning is kept on disk;
read the issues first. The scientific record is the one exception: PROPOSAL.md, PREREGISTRATION.md and
RESULTS.md stay in the repository because a pre-registration has to be committed before its result is seen.

## 1. General principles

- Write clean, elegant, maintainable, modular code. Prefer explicitness over cleverness.
- Keep functions and modules small and focused. Do one thing, at one level of abstraction.
- Never write nested functions or classes.
- Avoid duplication. Reuse an existing utility before writing a new one.
- Readability and maintainability come before optimization. Measure before you optimize.
- Leave the code cleaner than you found it, within the scope of the change you are making.
- YAGNI: build what the current task needs, nothing speculative.

## 2. Clean Code, distilled

From Robert C. Martin's *Clean Code*. These are the rules we hold each other to.

### 2.1 Names

- Names reveal intent: a reader should know what a thing is, what it does and how it is used without a comment.
- Nouns for classes and variables, verbs for methods. `ResponseUNet`, `predict_field()`, `bundle_dir`.
- One word per concept across the codebase: do not mix `fetch`, `get` and `retrieve` for the same idea.
- Pronounceable, searchable names. No single-letter names outside tiny loops, no abbreviations, no type prefixes.
- Make meaningful distinctions. `record` and `records`, not `data` and `data2`.
- Pick names at the right level: `_disk()` inside a planner, `select_tiles()` facing the command line.

### 2.2 Functions

- Small. Then smaller. A function fits on one screen and does one thing.
- Zero to two arguments. Three needs a reason in a comment. More means an object is missing.
- No flag arguments. A boolean parameter means the function does two things; split it.
- No side effects a caller would not expect from the name. Separate commands (change state) from queries (answer).
- Do not return `None` to mean failure when a caller may forget to check, and never pass `None` as a sentinel.
- Extract `try` bodies into their own functions so error handling is one thing the function does.

### 2.3 Comments

- Comments explain why, never what. If the code needs a comment to say what it does, rename or restructure.
- Good comments: intent, consequences, a warning, a breadcrumb to related code or documentation, a legal header.
- No commented-out code. No noise comments that restate the signature. No journals or attributions.
- A `TODO` in code is not allowed. Create a GitHub issue instead and reference it if a pointer is needed.

### 2.4 Formatting

- The newspaper metaphor: a module reads top down, high level first, details below.
- Related things live close together. Declare a variable near its first use. Callers sit above callees.
- Blank lines separate concepts; no blank lines inside a concept.
- 119 columns for Python and Markdown alike. Formatting is automated with ruff; do not fight it.

### 2.5 Objects and data

- Data-only classes carry no policy. Policy classes do not expose their data.
- Law of Demeter: talk to friends, not strangers. No `a.get_b().get_c().do()` chains across objects you do not own.
- Use accessors and interface methods, never another class's internals, and never `isinstance` against a concrete
  class. Add a method that answers the question instead.

### 2.6 Error handling

- Every failure names the file, tile, layer, class code or parameter involved and chains the underlying exception
  with `from`.
- Catch the specific exceptions you can handle at that level. Never a bare `except` or `except Exception` without
  a comment saying why and re-raising or recording it.
- Never fail silently. No empty `except`, no swallowed return value, no "best effort" fallback that hides a defect.
- Define exception classes by what the caller needs to distinguish, not by where they were raised.

### 2.7 Boundaries

- Wrap third-party APIs behind our own small interfaces, so a library change touches one module.
- When adopting a library, write a learning test that pins the behavior we rely on. The tile addressing tests in
  `tests/test_geo.py` are one.

### 2.8 Tests

- TDD, three laws: write a failing test first, write only enough test to fail, write only enough code to pass.
- F.I.R.S.T.: fast, independent, repeatable, self-validating, timely.
- One concept per test, with a name that states the behavior. Assert on behavior, not on implementation details.
- Tests are first-class code: same naming, same structure, same lint. Test doubles live in `tests/support`.
- Cover the failure path with the same care as the happy path. A reviewer rejects a change whose error branch is
  untested.

### 2.9 Classes

- Single responsibility: a class has one reason to change. State that reason in its docstring.
- Cohesion: methods use most of the fields. When a subset of methods uses a subset of fields, split the class.
- Depend on abstractions. Inject collaborators through the constructor so a test can substitute them.
- Kent Beck's four rules of simple design, in order: passes all tests, no duplication, expresses intent, fewest
  classes and methods that achieve the first three.

### 2.10 Smells and heuristics

The checklist from the last chapter of *Clean Code*, trimmed to what we meet in this codebase.

- Obvious behavior is unimplemented: a function named `daylight_mean` that silently drops an hour is a defect.
- Boundary conditions: find every edge (empty, one, many, missing, duplicate) and test it explicitly.
- Dead code, unused parameters and unreachable branches are removed.
- Vertical separation: define things close to where they are used; private helpers directly below their caller.
- Inconsistency: do the same thing the same way everywhere. If one reader raises `RuntimeError` on a missing land
  tile, all do.
- Artificial coupling: a constant, enum or helper lives where it is used, not in a shared "utils" module.
- Feature envy: a method that mostly manipulates another object's data belongs on that object.
- Selector arguments: no `mode` or boolean parameters that switch behavior; write two functions.
- Obscured intent: expand magic numbers and dense expressions into named constants and explanatory variables.
- Misplaced responsibility: put code where a reader would look for it, and name it so they find it.
- Prefer polymorphism to `if`/`elif` chains on type. Where the chain stays, keep it in one place.
- Encapsulate conditionals in a named method; avoid negative conditionals.
- No hidden temporal coupling: if the baseline must run before a plan is scored, make the order enforced or
  impossible to miss.
- Configurable data stays at the top (the intervention catalogue, the corpus), not buried in a low-level module.
- Tests: an ignored or skipped test is an open question with an owner. Test near bugs exhaustively.
- Names describe side effects: `get_or_create()` rather than `get()` that also creates.

### 2.11 Concurrency

- Keep concurrency code in a few small places (`sim/runner.py`, the simulation lock in `surrogate/dataset.py`),
  not spread out.
- Limit shared mutable state and guard what remains with one lock per resource, taken in a fixed order.
- Enter and exit a context (a lock, a subprocess, an async context) in the same task. Hold long-lived contexts in
  a dedicated task with a stop event.
- Test concurrency paths on purpose, with overlapping calls, not by hoping they are rare.

## 3. The Clean Coder, distilled

From Robert C. Martin's *The Clean Coder*. How we behave, not what we type.

- Take responsibility. Do no harm to function (ship no known bugs) or to structure (leave no mess for later).
- Know your domain. Read the spec, the plan and the neighboring code before changing anything.
- Say no when something cannot be done well in the time or shape asked. Say what can be done instead.
- Say yes with commitment language: "I will have X by Y." Never "I'll try." If you cannot commit, say so early.
- Done means: lint passes, all tests pass, documentation is updated, the issue is updated, the PR is mergeable.
  There is no "done except for".
- Do not code tired, rushed or angry. Under pressure, slow down and follow the disciplines harder, not less.
- Estimate honestly, in ranges. Report slips the moment you see them, not at the deadline.
- Avoid blind alleys. When an approach fights back, stop, say so, and reconsider rather than sinking more time.
- Practice. Spikes and throwaway experiments are fine and encouraged, as long as they stay labeled throwaway.
- Collaborate. Ask early, review generously, and leave reviewers enough context to review without you.

## 4. Python style

- Python 3.12. uv manages the project: `uv sync`, `uv run <command>`, `uv.lock` committed.
- PEP 8. Imports in three groups (standard library, third party, local), one import per line, sorted by ruff's
  isort with `force-single-line`.
- Explicit type hints on every parameter and return value. Annotate assignments whose type is not obvious.
- `snake_case` for functions, methods, variables and attributes; `PascalCase` for classes; `UPPER_CASE` for
  constants. Comment the reason when an external API forces another convention.
- Dictionary reads use `.get()`, never `dict[key]`.
- Logging, never `print`, except for the CLI's own output. Lazy `%` formatting: `logger.info("Loaded %s", name)`.
  Never log secrets, credentials or fixture contents at info level.
- Blocking I/O inside async code goes through `asyncio.to_thread()`; never block the event loop.
- Long-form flags only (`--force`, not `-f`).
- Commands that answer a question take `--json`: one document on stdout, logs on stderr. Commands that show a
  dashboard write their results to disk instead, where the question commands read them. A command that cannot
  do what was asked ends through `exit_codes.fail`: 1 when the work could not be done, 2 when the command line
  was wrong, 130 when stopped.
- Linting: `ruff format`, `ruff check`, then `pyrefly check`. Configuration lives in `.ruff.toml` and
  `pyrefly.toml`. A lint failure is a build failure.

## 5. Module design

- One module, one responsibility, one class, named after it. Every dataclass, exception and protocol has its
  own file. Type aliases may share a small `*_types.py` module.
- `__init__.py` files are empty. No docstring, no imports, no code.
- No global mutable state. Module-level constants are fine.
- Group related modules into packages by responsibility: `data`, `sim`, `surrogate`, `baselines`, `experiments`,
  `network`, `service`, `server`.
- `sim/` is the only package that knows the physics engine exists, and it reaches it as a subprocess. Nothing
  under `src/` imports `solweig_gpu`, which is GPL-3.0.
- The command line answers `--help` in a fraction of a second. A command module (`cli.py`, `*_cli.py`) imports
  typer, rich, the standard library and the light request, exception, console and path modules at the top; the
  service a command runs is imported inside the command. `tests/test_startup.py` guards it.
- The client is built into `src/shadecast/server/static/` by `make frontend` and is never committed. The
  hand-written pages that GitHub Pages publishes live in `src/shadecast/pages/`.

## 6. Documentation

- Documentation ships in the same PR as the behavior it describes.
- US spelling.
- No em-dashes anywhere: not in docs, commit messages, issue text, code or comments. Use a comma, period or colon.
- Verify every link in a document you touch.

## 7. Git, commits and pull requests

- Never commit to `main`. Branch per task: `task/<n>-<short-name>`, or `fix/<short-name>`, `docs/<short-name>`.
- One commit per single task or single file. Never bundle unrelated changes.
- Single-line commit messages in the imperative: `Defer heavy imports so the command line starts fast`.
  No body, no prefix tags.
- No `Co-Authored-By` trailer, ever. No "Generated with" footer or any tool attribution in commits or PR text.
- Open a PR for every branch and reference its issue (`Closes #<n>`). Merge into `main` with a merge commit, then
  sync local `main`.
- Before opening a PR: review the diff, remove debug output, stray files and anything touched by accident.
- Anything deliberately left out of a PR becomes an issue before the PR merges.

## 8. Issues and triage

Work is tracked in GitHub issues. The design spec is the parent issue; each spec section is a sub-issue; each
implementation task is a sub-issue of its design section. A task issue body starts with `Design section: #<n>`.
Issue titles never contain a slash.

| Label | Meaning |
|-------|---------|
| `needs-triage` | A maintainer still has to evaluate this issue |
| `needs-info` | Waiting on the reporter for more information |
| `ready-for-agent` | Fully specified, an agent can implement it unattended |
| `ready-for-human` | Requires human implementation or a decision |
| `wontfix` | Will not be actioned |
| `bug`, `enhancement` | Category labels, used alongside the triage labels |

Conventions for the `gh` CLI:

- Create: `gh issue create --title "..." --body-file <file> --label ... --milestone ...`, then attach it as a
  sub-issue: `gh api -X POST repos/deepsaia/shadecast/issues/<parent>/sub_issues -F sub_issue_id=<id>`,
  where `<id>` is the database id from `gh api repos/deepsaia/shadecast/issues/<n> --jq .id`.
- Read: `gh issue view <n> --comments`. Comment: `gh issue comment <n> --body "..."`.
- Labels: `gh issue edit <n> --add-label "..."` and `--remove-label "..."`.
- Close: `gh issue close <n> --comment "..."`.

## 9. Commands

```bash
make sync              # uv sync
make lint              # ruff format, ruff check --fix, pyrefly check
make test              # lint, then pytest (no network, no engine)
make engine            # the GPL physics engine in its own environment, .venv-engine
```

CLI usage is documented in `README.md` and specified in the design issue.
