---
name: launchd
description: Create, update, diagnose, and verify macOS launchd LaunchAgents and LaunchDaemons. Use when scheduling local commands with launchctl, writing plist jobs, or troubleshooting jobs that work interactively but fail under launchd.
---

# Reliable launchd jobs

Build the job the user requested and prove it works in launchd's real execution environment. A valid plist or successful `bootstrap` is not completion.

## Choose the correct scope

- Use a per-user LaunchAgent in `~/Library/LaunchAgents` for ordinary user tasks.
- Use a system LaunchDaemon only when the user explicitly needs a system-wide or pre-login job and authorizes the required administrator changes.
- Inspect existing plist files and `launchctl print` before choosing a label or replacing a job. Update an existing matching job instead of creating a duplicate.
- Preserve the user's requested scheduler. Do not replace an explicit launchd request with another automation system.

## Preflight macOS privacy before installing

launchd does not inherit Full Disk Access or Files & Folders permissions from Terminal, Ghostty, Codex, or another interactive parent app.

Before creating the job, identify every path and application data store it must read or write. Treat these as likely TCC-protected:

- `~/Documents`, `~/Desktop`, and `~/Downloads`;
- Chrome, Safari, Mail, Messages, and other apps' data under `~/Library`;
- browser cookies, credentials, and databases owned by another app.

Keep scripts, working files, and logs in an unprotected runtime location such as `~/Library/Application Support/<job-name>` or `~/Library/Logs/<job-name>`. Do not assume a symlink bypasses TCC. If the required final destination is protected, test writing there from the actual launchd job before declaring the design viable.

When protected data is unavoidable:

1. Identify the exact executable that performs the protected access.
2. Explain the minimum macOS permission the user must grant and why.
3. Do not bypass TCC with privilege escalation, copy browser credentials into a plist, or persist cookies/tokens unless the user explicitly chooses that design after the security tradeoff is explained.
4. Do not open or drive a GUI terminal, install an extension, or change Privacy & Security settings without the required user authorization.

If permission must be granted manually, prepare the job but leave it disabled or unloaded after a failed test. Do not leave a known-broken job scheduled to fail repeatedly.

## Make the job independent of an interactive shell

- Use absolute executable and file paths. Never rely on shell startup files, aliases, Homebrew being on `PATH`, or the current working directory.
- Put nontrivial logic in a separate executable script rather than an opaque plist argument list.
- Give the job explicit stdout and stderr log paths.
- For shell scripts, use strict error handling such as `set -euo pipefail` when compatible with the command.
- Protect backup integrity: write to a unique temporary file on the destination filesystem, validate it, set intended permissions, then atomically rename it to the final name. Clean temporary files on failure.
- Quote paths and data. Never expose secrets through logs or process arguments when a safer mechanism exists.

For timestamped backups, calculate the timestamp when the job runs, not when installing it. Use a collision-resistant format requested by the user, such as `date '+%Y%m%d-%H%M%S'`.

## Install and test

Validate before loading:

```bash
plutil -lint /absolute/path/to/job.plist
/bin/zsh -n /absolute/path/to/job-script.sh
```

For a user LaunchAgent, operate in `gui/$(id -u)`. When updating a loaded job, boot out the exact existing label before bootstrapping the revised plist. Then enable and kick-start the exact service label.

After the manual kick-start:

1. Wait for the process to finish when it is expected to be short-lived.
2. Inspect `launchctl print gui/$(id -u)/<label>` for state, run count, and last exit code.
3. Read both logs.
4. Verify the intended artifact exists, has the expected filename, is nonempty, and passes format-specific validation.
5. Confirm no partial or temporary output remains.
6. Confirm the printed calendar or interval trigger matches the user's requested schedule and local-time expectation.

Common signals:

- Exit 126 or 127, “can't open input file,” or “operation not permitted” usually means an unreadable path, missing executable, or TCC denial—not a plist success.
- A credential or browser-cookie command that works in Ghostty but fails under launchd is a privacy-context problem until proven otherwise.
- Repeated kick-starts do not fix permissions. Stop after one diagnostic retry with a materially changed setup.

## Completion standard

Call the work complete only when all of these are true:

- the intended job is loaded and enabled;
- a launchd-triggered test exits successfully;
- logs contain no unresolved error;
- the requested output is present and validated;
- the installed trigger matches the schedule.

If any condition fails, report the job as blocked or partially installed, state whether it is loaded or disabled, give the exact evidence, and request only the minimum user action needed to continue.
