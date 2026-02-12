# Contributing to PhilReview

PhilReview is a multi-agent system that generates academic literature reviews for philosophy research. Contributions that improve accuracy, coverage, rigor, or usability are welcome.

## Getting Started

1. Fork the repository and clone your fork
2. Set up your environment:
   ```bash
   uv sync
   python .claude/skills/philosophy-research/scripts/check_setup.py
   ```
   See `GETTING_STARTED.md` for API key configuration and platform-specific details.
3. Run the test suite to confirm everything works:
   ```bash
   pytest tests/
   ```

## What to Contribute

Anything that improves the project in line with its objectives—accuracy first, then comprehensiveness, rigor, and reproducibility. Examples:

- **Bug fixes** — Broken API scripts, hook failures, cross-platform issues
- **Agent and skill improvements** — Better prompts, search strategies, synthesis quality
- **New academic source integrations** — Additional APIs in `.claude/skills/philosophy-research/`
- **Hook and validation improvements** — Stricter BibTeX validation, better error handling
- **Token efficiency** — Reducing API costs without sacrificing review quality
- **Platform compatibility** — Fixing platform-specific issues, making the tool available on more systems
- **Tests** — Expanded coverage for API scripts, hooks, and workflow phases
- **Documentation** — Corrections, clarifications, setup guides

## How to Contribute

### Reporting Bugs and Requesting Features

Open a [GitHub Issue](https://github.com/AI-4-Phi/PhilReview/issues). For bug reports, include:

- What you did (the prompt or command)
- What happened (error output, unexpected behavior)
- What you expected
- Your platform (macOS, Linux, Windows) and Python version

### Submitting Changes

1. Fork the repository
2. Create a branch from `main` for your changes
3. Make your changes
4. Run `pytest tests/` and confirm all tests pass
5. Open a pull request against `main`

PRs are reviewed by the maintainers (Johannes Himmelreich and Marco Meyer). We aim to respond within a week.

### PR Guidelines

- Keep PRs focused. One fix or feature per PR.
- Follow the project principles below.
- If adding a Python dependency, update all four locations listed under "Adding Python Dependencies" in `CLAUDE.md`.
- If modifying agents or skills, test with an actual literature review run—not just unit tests.

## Architecture

The 6-phase workflow, agent definitions, and design patterns are documented in `.claude/docs/ARCHITECTURE.md`. Read this before modifying agents or skills.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
