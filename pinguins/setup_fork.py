#!/usr/bin/env python3
"""
Μία φορά, στη ρίζα του fork (branch από το tag 1.4.9):

    python3 pinguins/setup_fork.py

- Βάζει βήμα "Pinguins branding" μετά το checkout στα jobs Windows + Linux
- Απενεργοποιεί jobs που δεν χρειαζόμαστε (macOS, iOS, Android, sciter, flatpak, appimage)
- Σβήνει τα υπόλοιπα workflows του upstream (nightly cron, CI σε κάθε push κ.λπ.)
- Γράφει το .github/workflows/pinguins-build.yml (χειροκίνητο build + release)
Idempotent: αν ξανατρέξει, δεν διπλασιάζει τίποτα.
"""
import os
import re
import sys

WF = ".github/workflows"
BUILD = f"{WF}/flutter-build.yml"
KEEP = {"flutter-build.yml", "bridge.yml", "third-party-RustDeskTempTopMostWindow.yml", "pinguins-build.yml"}
BRAND_JOBS = ["build-for-windows-flutter", "build-rustdesk-linux"]
DISABLE_JOBS = [
    "build-for-windows-sciter", "build-rustdesk-ios", "build-for-macOS", "publish_unsigned",
    "build-rustdesk-android", "build-rustdesk-android-universal", "build-rustdesk-linux-sciter",
    "build-appimage", "build-flatpak", "build-rustdesk-web",
]
STEP_MARK = "      - name: Pinguins branding\n"
BRAND_STEP = (
    STEP_MARK
    + "        shell: bash\n"
    + "        env:\n"
    + "          PINGUINS_SERVER: ${{ vars.PINGUINS_SERVER }}\n"
    + "          PINGUINS_KEY: ${{ vars.PINGUINS_KEY }}\n"
    + "        run: python3 pinguins/brand.py\n"
    + "\n"
)

if not os.path.isfile(BUILD) or not os.path.isfile("pinguins/brand.py"):
    sys.exit("Τρέξε το από τη ρίζα του fork, αφού αντιγράψεις μέσα τον φάκελο pinguins/")

lines = open(BUILD, encoding="utf-8").read().split("\n")
JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
jobs_start = lines.index("jobs:")


def job_span(name):
    start = None
    for i in range(jobs_start + 1, len(lines)):
        m = JOB_RE.match(lines[i])
        if m and start is None and m.group(1) == name:
            start = i
        elif m and start is not None:
            return start, i
    if start is None:
        sys.exit(f"ΣΦΑΛΜΑ: δεν βρέθηκε job '{name}' στο {BUILD}")
    return start, len(lines)


# 1) απενεργοποίηση jobs (job-level `if:` είναι σε εσοχή 4 κενών)
for name in DISABLE_JOBS:
    s, e = job_span(name)
    body = [l for l in lines[s + 1:e] if not re.match(r"^    if:", l)]
    lines[s + 1:e] = ["    if: false  # PINGUINS: disabled"] + body

# 2) βήμα branding μετά το πρώτο checkout με submodules
for name in BRAND_JOBS:
    s, e = job_span(name)
    block = "\n".join(lines[s:e])
    if STEP_MARK in block + "\n":
        continue
    for i in range(s, e):
        if lines[i].strip() == "submodules: recursive":
            j = i + 1
            while j < e and lines[j].strip() == "":
                j += 1
            lines[j:j] = BRAND_STEP.rstrip("\n").split("\n") + [""]
            break
    else:
        sys.exit(f"ΣΦΑΛΜΑ: δεν βρέθηκε checkout στο job {name}")

open(BUILD, "w", encoding="utf-8").write("\n".join(lines))

# 3) σβήσιμο άλλων workflows
for fn in sorted(os.listdir(WF)):
    if fn not in KEEP and fn.endswith((".yml", ".yaml")):
        os.remove(os.path.join(WF, fn))
        print("removed", fn)

# 4) δικό μας workflow
ver = re.search(r'^  VERSION: "([^"]+)"', open(BUILD, encoding="utf-8").read(), re.M).group(1)
open(f"{WF}/pinguins-build.yml", "w", encoding="utf-8").write(f"""name: Pinguins Hub build

on:
  workflow_dispatch:
    inputs:
      tag:
        description: "Release tag"
        required: true
        default: "pinguins-hub-{ver}"

permissions:
  contents: write

jobs:
  build:
    uses: ./.github/workflows/flutter-build.yml
    secrets: inherit
    with:
      upload-artifact: true
      upload-tag: ${{{{ inputs.tag }}}}

  rename-assets:
    needs: build
    if: ${{{{ always() }}}}
    runs-on: ubuntu-latest
    steps:
      - name: rustdesk-* -> pinguins-hub-*
        env:
          GH_TOKEN: ${{{{ github.token }}}}
          TAG: ${{{{ inputs.tag }}}}
        run: |
          set -e
          rid=$(gh api repos/$GITHUB_REPOSITORY/releases/tags/$TAG -q .id)
          gh api repos/$GITHUB_REPOSITORY/releases/$rid/assets --paginate -q '.[] | "\\(.id) \\(.name)"' |
          while read -r id name; do
            case "$name" in
              rustdesk-*) new="pinguins-hub-${{name#rustdesk-}}"
                gh api -X PATCH repos/$GITHUB_REPOSITORY/releases/assets/$id -f name="$new" >/dev/null
                echo "$name -> $new";;
            esac
          done
""")
print(f"OK: {BUILD} patched, pinguins-build.yml written (version {ver})")
