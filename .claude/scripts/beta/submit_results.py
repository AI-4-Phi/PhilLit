#!/usr/bin/env python3
"""
Stop hook for PhilReview beta testing.

Triggered after every Claude response. Checks for completion markers and
uploads review data to B2 for analysis.

Behavior:
1. Check for .philreview_complete marker in any reviews/*/ directory
2. If no marker: exit silently (normal case)
3. If marker found:
   - Upload *.md and *.bib files from that review directory to B2
   - Upload metadata.json with review_id, session_id, tester_id, version, status
   - Delete marker after successful upload
   - Open feedback survey in browser
   - Output JSON with decision="block" so Claude presents the survey URL
     to the user conversationally (stdout from Stop hooks is only visible
     in verbose mode, so we use the block mechanism to relay the survey
     through Claude's response instead)

Environment variables:
- PHILREVIEW_TESTER_ID (required)
- B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY (required for upload)
- PHILREVIEW_B2_BUCKET (required)
- PHILREVIEW_QUALTRICS_URL (required for survey)
- PHILREVIEW_VERSION (set by update script)
"""

import html
import json
import os
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from b2sdk.v2 import B2Api, InMemoryAccountInfo
from b2sdk.v2.exception import B2Error


def load_dotenv(env_file: Path) -> None:
    """Load environment variables from .env file.

    Stop hooks don't inherit environment variables persisted via CLAUDE_ENV_FILE
    during SessionStart, so we need to load the .env file directly.
    """
    if not env_file.exists():
        return

    for line in env_file.read_text().splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue

        # Parse KEY=VALUE
        if '=' in line:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()

            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            # Only set if not already in environment (don't override)
            if key and key not in os.environ:
                os.environ[key] = value


def get_script_dir() -> Path:
    """Get directory containing this script."""
    return Path(__file__).resolve().parent


def get_project_root() -> Path:
    """Get project root (3 levels up from .claude/scripts/beta/)."""
    return get_script_dir().parent.parent.parent



def get_git_version(cwd: Path) -> str:
    """Get current git short hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except subprocess.SubprocessError:
        return "unknown"



def find_completion_markers(project_root: Path) -> list[Path]:
    """Find all .philreview_complete markers in reviews/*/."""
    reviews_dir = project_root / "reviews"
    if not reviews_dir.exists():
        return []

    markers = []
    for review_dir in reviews_dir.iterdir():
        if review_dir.is_dir():
            marker = review_dir / ".philreview_complete"
            if marker.exists():
                markers.append(marker)
    return markers


def get_b2_bucket(bucket_name: str, key_id: str, app_key: str):
    """Authorize with B2 and return the bucket object.

    Returns the bucket on success, or None on failure.
    """
    try:
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", key_id, app_key)
        return b2_api.get_bucket_by_name(bucket_name)
    except B2Error as e:
        print(f"B2 authorization failed: {e}", file=sys.stderr)
        return None


def upload_to_b2(bucket, local_path: Path, remote_path: str) -> bool:
    """Upload a file to B2 bucket using the SDK."""
    try:
        bucket.upload_local_file(
            local_file=str(local_path),
            file_name=remote_path,
        )
        return True
    except B2Error as e:
        print(f"B2 upload failed for {local_path.name}: {e}", file=sys.stderr)
        return False


def handle_survey(review_id: str, tester_id: str, review_name: str) -> str | None:
    """Build survey URL, open browser, and return URL for Claude to present.

    Returns the survey URL on success, None if not configured.
    """
    qualtrics_url = os.environ.get("PHILREVIEW_QUALTRICS_URL")
    if not qualtrics_url:
        print("Survey URL not configured (PHILREVIEW_QUALTRICS_URL)", file=sys.stderr)
        return None

    # Build survey URL with review_id, tester_id, and review_name parameters
    separator = "&" if "?" in qualtrics_url else "?"
    survey_url = (
        f"{qualtrics_url}{separator}"
        f"review_id={quote(review_id)}&tester_id={quote(tester_id)}&review_name={quote(review_name)}"
    )

    # Open browser
    try:
        webbrowser.open(survey_url)
        print("Survey opened in browser", file=sys.stderr)
    except Exception as e:
        print(f"Could not open browser: {e}", file=sys.stderr)

    return survey_url


def write_survey_files(review_dir: Path, survey_url: str) -> None:
    """Write feedback-survey.html and FEEDBACK-SURVEY.md into the review directory.

    These files give the user a persistent, clickable way to access the
    feedback survey after they have had time to read through the review.
    """
    safe_url = html.escape(survey_url, quote=True)

    html_content = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PhilReview Feedback Survey</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
    max-width: 540px;
    margin: 80px auto;
    padding: 0 20px;
    color: #333;
    line-height: 1.5;
  }}
  h1 {{ font-size: 1.4em; }}
  .btn {{
    display: inline-block;
    margin: 24px 0;
    padding: 12px 28px;
    background: #2563eb;
    color: #fff;
    text-decoration: none;
    border-radius: 6px;
    font-size: 1em;
  }}
  .btn:hover {{ background: #1d4ed8; }}
  .note {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>PhilReview Feedback Survey</h1>
<p>
  Thank you for completing a literature review with PhilReview.
  Please take a few minutes to share your feedback once you have
  read through the review.
</p>
<a class="btn" href="{safe_url}">Open Survey</a>
<p class="note">The survey takes about 6&ndash;8 minutes.</p>
</body>
</html>
"""

    md_content = f"""\
# PhilReview Feedback Survey

Thank you for completing a literature review with PhilReview.
Please take a few minutes to share your feedback once you have
read through the review.

**[Open Survey]({survey_url.replace(")", "%29")})**

The survey takes about 6-8 minutes.
"""

    for name, content in [
        ("feedback-survey.html", html_content),
        ("FEEDBACK-SURVEY.md", md_content),
    ]:
        path = review_dir / name
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            print(f"Warning: Could not write {name}: {e}", file=sys.stderr)


def process_marker(marker_path: Path) -> tuple[bool, str | None]:
    """Process a completion marker: upload files and handle survey.

    Returns (success, survey_url). survey_url is None on failure or if
    the survey URL is not configured.
    """
    review_dir = marker_path.parent

    # Read marker data
    try:
        marker_data = json.loads(marker_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading marker: {e}", file=sys.stderr)
        return False, None

    review_id = marker_data.get("review_id", "unknown")
    status = marker_data.get("status", "unknown")

    # Get required environment variables
    tester_id = os.environ.get("PHILREVIEW_TESTER_ID")
    if not tester_id:
        print("Error: PHILREVIEW_TESTER_ID not set", file=sys.stderr)
        return False, None

    bucket_name = os.environ.get("PHILREVIEW_B2_BUCKET")
    if not bucket_name:
        print("Error: PHILREVIEW_B2_BUCKET not set", file=sys.stderr)
        return False, None
    version = os.environ.get("PHILREVIEW_VERSION") or get_git_version(get_project_root())

    # Check B2 credentials
    key_id = os.environ.get("B2_APPLICATION_KEY_ID")
    app_key = os.environ.get("B2_APPLICATION_KEY")
    if not key_id or not app_key:
        print("Error: B2 credentials not set (B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)", file=sys.stderr)
        return False, None

    # Authorize and get bucket
    bucket = get_b2_bucket(bucket_name, key_id, app_key)
    if bucket is None:
        return False, None

    # Build remote path prefix
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    remote_prefix = f"{tester_id}/{review_id}/{timestamp}"

    # Collect files to upload (*.md, *.bib, and intermediate_files/)
    files_to_upload: list[tuple[Path, str]] = []

    # Main directory files
    for pattern in ["*.md", "*.bib"]:
        for f in review_dir.glob(pattern):
            if f.is_file():
                remote_path = f"{remote_prefix}/{f.name}"
                files_to_upload.append((f, remote_path))

    # Intermediate files (if they exist)
    intermediate_dir = review_dir / "intermediate_files"
    if intermediate_dir.exists():
        for f in intermediate_dir.rglob("*"):
            if f.is_file():
                relative = f.relative_to(review_dir)
                remote_path = f"{remote_prefix}/{relative}"
                files_to_upload.append((f, remote_path))

    # Create and upload metadata
    metadata = {
        "review_id": review_id,
        "tester_id": tester_id,
        "version": version,
        "status": status,
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "marker_data": marker_data,
        "files_uploaded": [str(f[1]) for f in files_to_upload]
    }

    metadata_path = get_script_dir() / "metadata_temp.json"
    try:
        metadata_path.write_text(json.dumps(metadata, indent=2))
        files_to_upload.append((metadata_path, f"{remote_prefix}/metadata.json"))
    except OSError as e:
        print(f"Error writing metadata: {e}", file=sys.stderr)
        return False, None

    # Upload all files (progress to stderr so stdout stays clean for JSON)
    print(f"Uploading review data for {review_id}...", file=sys.stderr)
    upload_success = True
    for local_path, remote_path in files_to_upload:
        if not upload_to_b2(bucket, local_path, remote_path):
            upload_success = False

    # Clean up temp metadata file
    try:
        metadata_path.unlink()
    except OSError:
        pass

    if upload_success:
        print(
            f"Upload complete: {len(files_to_upload)} files uploaded to "
            f"{bucket_name}/{remote_prefix}/",
            file=sys.stderr,
        )

        # Delete marker after successful upload
        try:
            marker_path.unlink()
            # Also delete review_id file
            review_id_file = review_dir / ".philreview_review_id"
            if review_id_file.exists():
                review_id_file.unlink()
        except OSError as e:
            print(f"Warning: Could not delete marker: {e}", file=sys.stderr)

        # Handle survey
        review_name = review_dir.name
        survey_url = handle_survey(review_id, tester_id, review_name)

        # Write persistent survey files into the review directory
        if survey_url:
            write_survey_files(review_dir, survey_url)

        return True, survey_url
    else:
        print("Some files failed to upload. Marker retained for retry.", file=sys.stderr)
        return False, None


def main() -> int:
    """Main entry point.

    Outputs JSON to stdout when a review was completed and a survey should
    be presented. The JSON uses decision="block" to prevent Claude from
    stopping, so it can relay the survey URL to the user conversationally.
    On the next Stop event the marker will be gone and the script exits
    silently, allowing Claude to stop.
    """
    project_root = get_project_root()

    # Load .env file - Stop hooks don't inherit CLAUDE_ENV_FILE environment
    load_dotenv(project_root / ".env")

    # Find completion markers
    markers = find_completion_markers(project_root)

    if not markers:
        # No markers found - this is the normal case, exit silently
        return 0

    # Process each marker (typically just one).
    # Upload failures are logged to stderr by process_marker; we don't
    # branch on success here because the marker is retained for retry
    # on failure and we must always exit 0 (the hook system only parses
    # JSON stdout when exit code is 0).
    survey_urls = []
    for marker in markers:
        _, survey_url = process_marker(marker)
        if survey_url:
            survey_urls.append(survey_url)

    if survey_urls:
        # Block Claude from stopping so it presents the survey to the user.
        survey_url = survey_urls[0]
        reason = (
            "The literature review has been completed and all review data "
            "has been uploaded successfully. Please tell the user:\n\n"
            "1. Their literature review is complete and has been saved.\n"
            "2. Please complete the feedback survey — it takes about 6-8 "
            "minutes and helps improve PhilReview.\n"
            f"3. Survey link: {survey_url}\n"
            "4. The survey has also been opened in their browser.\n"
            "5. If they prefer to take the survey later (e.g. after reading "
            "through the review), they can find a clickable link saved in "
            "their review folder: feedback-survey.html (double-click to "
            "open) or FEEDBACK-SURVEY.md.\n\n"
            "Keep the message brief and friendly."
        )
        output = {"decision": "block", "reason": reason}
        print(json.dumps(output))

    # Exit 0 unconditionally: the hook system only parses JSON stdout
    # on exit 0, and upload failures are already logged to stderr and
    # retried on next run (markers are retained).
    return 0


if __name__ == "__main__":
    sys.exit(main())
