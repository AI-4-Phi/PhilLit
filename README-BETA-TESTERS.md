# PhilReview Beta Testing Guide

Thank you for participating in the PhilReview beta test. This guide will help you set up your environment and run literature reviews.

## Prerequisites

Before starting, ensure you have:

- **Claude Code**: Install via `npm install -g @anthropic-ai/claude-code`
- **Git**: For cloning and receiving updates
- **Python 3.10+**: For running scripts
- **uv**: Python package manager (`pip install uv` or `brew install uv`)

## Setup Steps

### 1. Clone the Repository

```bash
git clone -b beta-testing https://github.com/[repo]/philo-sota.git
cd philo-sota
```

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Add Your Environment File

You will receive a personalized environment file (`.env`) from the research team with your credentials pre-filled.

Copy this file to your philo-sota repository root:

```bash
# The file should be at:
philo-sota/.env
```

This file is gitignored and will be loaded automatically by Claude Code when you start a session.

### 4. Verify Setup

Start Claude Code using the provided launcher script:

```bash
# macOS/Linux
cd philo-sota
./start-claude.sh

# Windows (PowerShell)
cd philo-sota
.\start-claude.ps1
```

The launcher loads your `.env` file before starting Claude Code, ensuring telemetry is properly configured. You should see "Python environment ready" in the output.

> **Important:** Always use the launcher script (`start-claude.sh` or `start-claude.ps1`) instead of running `claude` directly. Claude Code initializes telemetry at startup, before any hooks run. The launcher ensures your credentials are loaded first. If you run `claude` directly, the setup hook will fail with an error message explaining how to fix it, and you'll need to restart using the launcher.

## Environment Variables

Your .env file configures these variables:

### Required

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your workspace-specific API key |
| `PHILREVIEW_TESTER_ID` | Your tester identifier (e.g., `tester-01`) |

### File Upload (for data collection)

| Variable | Description |
|----------|-------------|
| `B2_APPLICATION_KEY_ID` | Backblaze key ID |
| `B2_APPLICATION_KEY` | Backblaze application key |
| `PHILREVIEW_B2_BUCKET` | Bucket name |

### Survey (for feedback)

| Variable | Description |
|----------|-------------|
| `PHILREVIEW_QUALTRICS_URL` | Survey URL base |

### Telemetry (for debugging/analytics)

| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_ENABLE_TELEMETRY` | Set to `1` to enable |
| `OTEL_METRICS_EXPORTER` | Set to `otlp` |
| `OTEL_LOGS_EXPORTER` | Set to `otlp` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Set to `http/protobuf` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Grafana Cloud endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | Base64 auth token |
| `OTEL_LOG_USER_PROMPTS` | Set to `1` |
| `OTEL_RESOURCE_ATTRIBUTES` | Includes tester.id, project, version |

### Auto-detected

| Variable | Description |
|----------|-------------|
| `PHILREVIEW_VERSION` | Current git commit (read from git at upload time) |

## Running a Literature Review

### 1. Start Claude Code

```bash
# macOS/Linux
./start-claude.sh

# Windows (PowerShell)
.\start-claude.ps1
```

The launcher loads your credentials and starts Claude Code. The auto-update hook will check for updates and sync dependencies if needed.

### 2. Request a Literature Review

In the Claude Code session:

```
I'd like a literature review on [your research topic].

[Describe your research question, key concepts, and any specific areas of focus.]
```

Claude will invoke the `/literature-review` skill and guide you through the 6-phase workflow.

### 3. Review Outputs

When complete, your review will be in `reviews/[topic-name]/`:

- `literature-review-final.md` - The completed review
- `literature-all.bib` - Aggregated bibliography (importable to Zotero)
- `intermediate_files/` - Workflow artifacts

### 4. Provide Feedback

After each review, you'll be prompted to complete a feedback survey. This helps us improve PhilReview.

## Automatic Updates

PhilReview automatically checks for updates at session start:

- If you're on the `beta-testing` branch with no uncommitted changes, updates are applied automatically
- If dependencies change (`pyproject.toml` or `uv.lock`), `uv sync` runs automatically
- Your session always uses the latest version

## Troubleshooting

### "Environment verification failed"

Run the setup check manually:

```bash
python .claude/skills/philosophy-research/scripts/check_setup.py --json
```

This will show which components are missing or misconfigured.

### "B2 credentials not set"

Verify your .env file exists:

```bash
ls -la .env
```

If missing:
1. Copy the `.env` file you received to the repository root
2. Ensure the file is named exactly `.env` (with the leading dot)
3. Restart Claude Code to reload the environment

### "git pull failed"

If you have local changes preventing updates:

```bash
git stash
# Or discard changes:
git checkout .
```

### API Rate Limits

If you encounter rate limits during literature search:

- The domain researchers will retry automatically
- For persistent issues, wait a few minutes and resume the session
- The workflow saves progress, so you can continue where you left off

### Session Interrupted

If your session is interrupted mid-review:

1. Start a new Claude Code session
2. Request to continue the literature review
3. The workflow will detect `task-progress.md` and resume from the last completed phase

## Budget and Usage

Your Anthropic workspace has a usage limit. To check remaining budget:

1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Navigate to your workspace
3. View usage under "Billing"

If you approach your limit, contact the research team to request an increase.

## Support

For technical issues or questions:

- Email: [research team email]
- GitHub Issues: [repo]/issues (for non-sensitive issues)

## Privacy Note

The beta testing infrastructure collects:

- Completed literature reviews (uploaded to secure storage)
- Session telemetry (API calls, timing, errors)
- Survey responses

All data is used solely for improving PhilReview and is handled according to the consent agreement you signed. You may withdraw at any time by contacting the research team.
