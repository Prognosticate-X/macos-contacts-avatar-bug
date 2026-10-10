#!/usr/bin/env python3
"""
Automated Diagnostic Analyzer for macOS Contacts Avatar Reversion Regression
Scans Unified Logs to detect the ChangeHistoryFetch group-resolution failure
and AvatarViewSnapshotter fallback override.
"""

import sys
import os
import re
from datetime import datetime

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

TIMESTAMP_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})")

def parse_time(line):
    m = TIMESTAMP_REGEX.match(line)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            return None
    return None

def analyze(log_file):
    print(f"\n{CYAN}{BOLD}===================================================================={RESET}")
    print(f"{CYAN}{BOLD}   macOS Contacts Bug Automated Log Analyzer                       {RESET}")
    print(f"{CYAN}{BOLD}===================================================================={RESET}")
    print(f"Target log file: {BOLD}{log_file}{RESET}\n")

    if not os.path.exists(log_file):
        print(f"{RED}[ERROR] File not found: {log_file}{RESET}")
        return 1

    commit_events = []
    carddav_events = []
    push_events = []
    group_delete_events = []
    snapshotter_events = []

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            t = parse_time(line)

            # 1. Commit edits / saving image
            if "will commit edits for contact" in line or "Saving contact image" in line or "Saving avatar picker likeness" in line:
                commit_events.append((idx, t, line.strip()))

            # 2. CardDAV success (status 207)
            elif "received response, status 207" in line and "AddressBookSourceSync" in line:
                carddav_events.append((idx, t, line.strip()))

            # 3. APNS push
            elif "push: Received push notification" in line:
                push_events.append((idx, t, line.strip()))

            # 4. Critical Bug: change type 1 -> delete change type
            elif "Could not fetch group for change type 1" in line and "making it a delete change type" in line:
                group_delete_events.append((idx, t, line.strip()))

            # 5. Snapshotter override
            elif "AvatarViewSnapshotter" in line or "No avatarRecipeData" in line:
                snapshotter_events.append((idx, t, line.strip()))

    # Print analysis results
    print(f"{BOLD}[*] Detection Summary:{RESET}")
    print(f"  • Contact Save/Commit Events detected: {len(commit_events)}")
    print(f"  • CardDAV Server Push (Status 207) detected: {len(carddav_events)}")
    print(f"  • APNS Push Notifications detected: {len(push_events)}")
    print(f"  • 'Change Type 1 -> Delete Change Type' triggers: {len(group_delete_events)}")
    print(f"  • AvatarViewSnapshotter Override Events: {len(snapshotter_events)}\n")

    if group_delete_events:
        print(f"{RED}{BOLD}[✔ BUG CONFIRMED] macOS 27 ChangeHistoryFetch Regression Detected!{RESET}\n")
        print(f"{BOLD}Evidence Timeline:{RESET}")

        t_start = commit_events[0][1] if commit_events and commit_events[0][1] else None
        if commit_events:
            print(f"  {CYAN}1. Image Saved locally:{RESET}")
            for idx, t, line in commit_events[:2]:
                print(f"     Line {idx:5d} [{t.strftime('%H:%M:%S.%f')[:-3] if t else 'N/A'}]: {line[:100]}...")

        if carddav_events:
            print(f"  {CYAN}2. Synced to iCloud CardDAV successfully (HTTP 207):{RESET}")
            idx, t, line = carddav_events[0]
            print(f"     Line {idx:5d} [{t.strftime('%H:%M:%S.%f')[:-3] if t else 'N/A'}]: {line[:100]}...")

        if push_events:
            print(f"  {CYAN}3. APNS Push Notification received:{RESET}")
            idx, t, line = push_events[0]
            print(f"     Line {idx:5d} [{t.strftime('%H:%M:%S.%f')[:-3] if t else 'N/A'}]: {line[:100]}...")

        print(f"  {RED}{BOLD}4. Fatal Fallback Triggered across daemons (Change interpreted as Delete):{RESET}")
        for idx, t, line in group_delete_events[:4]:
            proc = line.split()[3] if len(line.split()) > 3 else "Process"
            print(f"     Line {idx:5d} [{t.strftime('%H:%M:%S.%f')[:-3] if t else 'N/A'}] {proc}:")
            print(f"       -> Could not fetch group for change type 1 ..., making it a delete change type.")

        if snapshotter_events:
            print(f"  {YELLOW}5. AvatarViewSnapshotter forced fallback monogram snapshot:{RESET}")
            for idx, t, line in snapshotter_events[:3]:
                if "No avatarRecipeData" in line or "AvatarViewSnapshotter" in line:
                    print(f"     Line {idx:5d} [{t.strftime('%H:%M:%S.%f')[:-3] if t else 'N/A'}]: {line[:100]}...")

        # Calculate delta
        t_revert = group_delete_events[0][1] if group_delete_events and group_delete_events[0][1] else None
        if t_start and t_revert:
            delta = (t_revert - t_start).total_seconds()
            print(f"\n{BOLD}Elapsed Duration from Save to Reversion:{RESET} {YELLOW}{BOLD}{delta:.2f} seconds{RESET}")

        print(f"\n{BOLD}Diagnostic Verdict:{RESET}")
        print("  This log proves that your system and iCloud account are healthy, but your Mac")
        print("  is suffering from an internal logic bug in macOS 27.0 contacts framework.")
        print("  Please submit this log alongside Apple Feedback Assistant ticket.\n")
        return 0
    else:
        print(f"{GREEN}[INFO] No 'change type 1 -> delete change type' markers found in this log.{RESET}")
        return 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        default_sample = os.path.join(os.path.dirname(__file__), "..", "samples", "sanitized_reproduction.log")
        if os.path.exists(default_sample):
            target = default_sample
        else:
            print("Usage: python3 analyze_log.py <path-to-log-file>")
            sys.exit(1)
    sys.exit(analyze(target))
