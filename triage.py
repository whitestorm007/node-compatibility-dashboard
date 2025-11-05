#!/usr/bin/env python3
# triage.py
#
# The main "runner" script.
# 1. Builds the Docker images
# 2. Reads libraries.txt
# 3. Calls test-harness.sh for each library
# 4. Gathers JSON output
# 5. Triages results
# 6. Generates report.md

import subprocess
import json
import os
import base64
from datetime import datetime

# --- Helper Functions ---

def build_docker_image(tag, dockerfile):
    """Builds a Docker image and shows output on failure."""
    print(f"Building {tag}...")
    try:
        # We've removed stdout/stderr suppression
        # We now capture stderr to print it on failure
        subprocess.run(
            ["docker", "build", "-t", tag, "-f", dockerfile, "."],
            check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as e:
        # This will now print the FULL error from Docker!
        print(f"FATAL: Docker build failed for {tag}\n")
        print("--- DOCKER ERROR ---")
        print(e.stderr)
        print("----------------------")
        exit(1)

def run_test_harness(url, lib_name):
    """Runs the harness script and captures its JSON output."""
    try:
        # Use subprocess.run to call the shell script
        result = subprocess.run(
            ['./test-harness.sh', url, lib_name],
            capture_output=True, text=True, check=True
        )
        # The script's output is a single line of JSON
        return json.loads(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error running harness for {lib_name}: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from harness for {lib_name}: {e}")
        return None

def decode_and_truncate_log(log_b64, lines=20):
    """Decodes base64 log and returns the last N lines."""
    if not log_b64:
        return "(No log output)"
    try:
        decoded_log = base64.b64decode(log_b64).decode('utf-8', 'errors=ignore')
        log_lines = decoded_log.strip().split('\n')
        # Return the last N lines
        return '\n'.join(log_lines[-lines:])
    except Exception as e:
        return f"(Error decoding log: {e})"

# --- Main Execution ---

def main():
    # Build Docker images first
    build_docker_image("node-stable", "stable.Dockerfile")
    build_docker_image("node-nightly", "nightly.Dockerfile")

    # Read the library list
    with open("libraries.txt", "r") as f:
        libraries = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    print(f"Starting tests for {len(libraries)} libraries...")
    
    results = []
    for i, url in enumerate(libraries):
        lib_name = url.split('/')[-1].replace('.git', '')
        print(f"({i+1}/{len(libraries)}) Testing {lib_name}...")
        result = run_test_harness(url, lib_name)
        if result:
            results.append(result)

    print("All tests complete. Generating report...")

    # --- Triage Results ---
    regressions = []
    broken = []
    untestable = []
    compatible = []

    for item in results:
        status = item['status']
        stable_pass = item['stable_pass'] == 0
        nightly_pass = item['nightly_pass'] == 0

        if status == "UNTESTABLE":
            untestable.append(item)
        elif status == "TESTED":
            if stable_pass and not nightly_pass:
                regressions.append(item)
            elif not stable_pass:
                broken.append(item)
            elif stable_pass and nightly_pass:
                compatible.append(item)
            # (The case 'not stable_pass and nightly_pass' is rare and ignored)

    # --- Generate report.md ---
    with open("report.md", "w") as f:
        f.write("# Node.js Nightly Compatibility Report\n\n")
        f.write(f"**Last Run:** {datetime.utcnow().isoformat()} UTC\n\n")
        
        total_tested = len(regressions) + len(broken) + len(compatible)
        if total_tested > 0:
            pass_rate = (len(compatible) / total_tested) * 100
            f.write(f"**Summary:** {len(compatible)} / {total_tested} testable libraries ({pass_rate:.2f}%) are compatible.\n\n")
        
        # 1. Regressions (The most important part)
        f.write(f"## 🚨 Regressions ({len(regressions)})\n")
        f.write("Libraries that **passed** on Node.js Stable but **failed** on Nightly.\n\n")
        for item in regressions:
            f.write(f"### 📦 {item['lib']}\n")
            f.write(f"* **Stable:** ✅ Pass\n")
            f.write(f"* **Nightly:** ❌ Fail\n")
            f.write("<details>\n<summary>Click to see Nightly Log (Last 20 lines)</summary>\n\n")
            f.write("```\n")
            f.write(decode_and_truncate_log(item['nightly_log']))
            f.write("\n```\n</details>\n\n")

        # 2. Already Broken
        f.write(f"## ⚠️ Already Broken ({len(broken)})\n")
        f.write("Libraries that **failed** on Node.js Stable. These failures are not related to Nightly.\n\n")
        for item in broken:
            f.write(f"### 📦 {item['lib']}\n")
            f.write(f"* **Stable:** ❌ Fail\n")
            f.write(f"* **Nightly:** {'❌ Fail' if item['nightly_pass'] != 0 else '✅ Pass'}\n")
            f.write("<details>\n<summary>Click to see Stable Log (Last 20 lines)</summary>\n\n")
            f.write("```\n")
            f.write(decode_and_truncate_log(item['stable_log']))
            f.write("\n```\n</details>\n\n")

        # 3. Compatible
        f.write(f"## ✅ Compatible ({len(compatible)})\n")
        f.write("Libraries that passed on both Stable and Nightly.\n\n")
        f.write("| Library | Status |\n")
        f.write("| --- | --- |\n")
        for item in compatible:
            f.write(f"| {item['lib']} | ✅ Pass |\n")

        # 4. Untestable
        f.write(f"\n## 🤷 Untestable ({len(untestable)})\n")
        f.write("Libraries that do not have a `scripts.test` in `package.json`.\n\n")
        f.write("| Library | Status |\n")
        f.write("| --- | --- |\n")
        for item in untestable:
            f.write(f"| {item['lib']} | 🤷 Untestable |\n")

    print("Report generated successfully: report.md")

if __name__ == "__main__":
    main()