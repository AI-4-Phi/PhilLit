# Contributing to PhilLit

PhilLit is a multi-agent system that generates academic literature reviews for philosophy research. Contributions that improve accuracy, coverage, rigor, or usability are welcome.

## Getting Started

1. Fork the repository and clone your fork
2. Set up your environment:
   ```bash
   uv sync          # installs all dependencies including dev (pytest)
   bash bin/phillit-run skills/philosophy-research/scripts/check_setup.py
   ```
   See `README.md` (Quick Start) and `.env.example` for API key configuration.
3. Run the test suite to confirm everything works:
   ```bash
   uv run --locked pytest
   ```
4. **Beta-test your changes as an end user would.** `--plugin-dir` loads your working tree as the installed plugin, so your uncommitted changes are picked up directly — no reinstall needed. Run it from a *scratch* directory, not the repo itself (running inside the repo is development mode, which does not register the skills/agents):
   ```bash
   # 1. Make a scratch workspace (persistent, so you can inspect the output afterward)
   mkdir -p ~/phillit-test && cd ~/phillit-test

   # 2. Launch Claude Code with your checkout loaded as the plugin
   claude --plugin-dir /path/to/your/PhilLit
   ```
   Then, inside that session:
   ```
   /phillit:setup
   ```
   `/phillit:setup` scaffolds the workspace (a `.phillit` marker, a `.env`, and merged permission rules). Add your API keys to the scratch `.env` (see `.env.example`), then request a review with `/phillit:literature-review`. Output lands in `reviews/<name>/` for you to inspect. Confirm the plugin loaded by typing `/` and checking that the `/phillit:*` commands appear. After editing plugin code, **restart the `claude` session** to reload it — the plugin is loaded at startup (a script or hook change also rebuilds the per-install venv on the next call if `pyproject.toml`/`uv.lock` changed).

## What to Contribute

Anything that improves the project in line with its objectives—accuracy first, then comprehensiveness, rigor, and reproducibility. Examples:

- **Bug fixes** — Broken API scripts, hook failures, cross-platform issues
- **Agent and skill improvements** — Better prompts, search strategies, synthesis quality
- **New academic source integrations** — Additional APIs in `skills/philosophy-research/`
- **Hook and validation improvements** — Stricter BibTeX validation, better error handling
- **Token efficiency** — Reducing API costs without sacrificing review quality
- **Platform compatibility** — Fixing platform-specific issues, making the tool available on more systems
- **Tests** — Expanded coverage for API scripts, hooks, and workflow phases
- **Documentation** — Corrections, clarifications, setup guides

## How to Contribute

### Reporting Bugs and Requesting Features

Open a [GitHub Issue](https://github.com/AI-4-Phi/PhilLit/issues). For bug reports, include:

- What you did (the prompt or command)
- What happened (error output, unexpected behavior)
- What you expected
- Your platform (macOS, Linux, Windows) and Python version

### Submitting Changes

1. Fork the repository
2. Create a branch from `main` for your changes
3. Make your changes
4. Run `uv run --locked pytest` and confirm all tests pass
5. Open a pull request against `main`

PRs are reviewed by the maintainers (Johannes Himmelreich and Marco Meyer). We aim to respond within a week.

### PR Guidelines

- Keep PRs focused. One fix or feature per PR.
- Follow the project principles below.
- If adding a Python dependency, update the locations listed under "Adding Python Dependencies" in `CLAUDE.md`.
- If modifying agents or skills, test with an actual literature review run (Getting Started, step 4)—not just unit tests.

## Architecture

The 6-phase workflow, agent definitions, and design patterns are documented in `docs/ARCHITECTURE.md`. Read this before modifying agents or skills.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
