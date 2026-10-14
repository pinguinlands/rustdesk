#!/usr/bin/env python3
"""
Pinguins Hub branding για RustDesk (δοκιμασμένο στο tag 1.4.9).

Τρέχει στη ρίζα του repo, ΜΕΤΑ το checkout (με submodules), πριν το build.
Χρησιμοποιεί μόνο stdlib — τρέχει σε Linux runner και σε Windows (Git Bash).

Αρχή: το ΤΕΧΝΙΚΟ όνομα μένει "RustDesk/rustdesk" (binary, service, φάκελοι config,
IPC, Wayland/uinput λογική), γιατί είναι δεμένο σε δεκάδες σημεία του κώδικα.
Αλλάζει ό,τι ΒΛΕΠΕΙ ο χρήστης: εικονίδια, logo, τίτλοι παραθύρων, tray, μεταφράσεις,
στοιχεία exe/deb — και μπαίνει ο δικός μας server + key.

Κάθε αντικατάσταση ελέγχεται: αν ένα pattern δεν βρεθεί ακριβώς όσες φορές
περιμένουμε, το script σταματάει με σφάλμα (καλύτερα να σπάσει το build παρά
να βγει μισο-branded client που μιλάει με τους public servers).

    python3 pinguins/brand.py            # εφαρμογή
    python3 pinguins/brand.py --check    # μόνο έλεγχος ότι όλα τα patterns βρίσκονται
"""
import os
import re
import shutil
import sys

ROOT = os.getcwd()
HERE = os.path.dirname(os.path.abspath(__file__))
CHECK_ONLY = "--check" in sys.argv
MARK = "PINGUINS_BRANDED"
errors = []


def load_config():
    cfg = {}
    with open(os.path.join(HERE, "config.env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    # Τα env vars (π.χ. GitHub secrets/vars) υπερισχύουν του config.env
    for k in list(cfg) + ["PINGUINS_SERVER", "PINGUINS_KEY"]:
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


cfg = load_config()
SERVER = cfg.get("PINGUINS_SERVER", "")
KEY = cfg.get("PINGUINS_KEY", "")
NAME = cfg.get("PINGUINS_DISPLAY_NAME", "Pinguins Hub")
COMPANY = cfg.get("PINGUINS_COMPANY", "Pinguins Land")
COPYRIGHT = cfg.get("PINGUINS_COPYRIGHT", "Copyright © Pinguins Land")
MAINTAINER = cfg.get("PINGUINS_MAINTAINER", "Pinguins Land <support@pinguin.land>")
HOMEPAGE = cfg.get("PINGUINS_HOMEPAGE", "https://pinguin.land")

# --- έλεγχοι εισόδου -----------------------------------------------------------
if not re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", SERVER):
    errors.append(f"PINGUINS_SERVER άκυρο: {SERVER!r}")
if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", KEY):
    errors.append("PINGUINS_KEY λείπει/άκυρο (θέλει το base64 public key του hbbs, 44 χαρακτήρες)")
for label, val in [("DISPLAY_NAME", NAME), ("COMPANY", COMPANY), ("COPYRIGHT", COPYRIGHT),
                   ("MAINTAINER", MAINTAINER), ("HOMEPAGE", HOMEPAGE)]:
    if any(c in val for c in '"\\\n'):
        errors.append(f"PINGUINS_{label} δεν επιτρέπεται να περιέχει \" ή \\")
if errors and not CHECK_ONLY:
    sys.exit("ΣΦΑΛΜΑ ρυθμίσεων:\n  " + "\n  ".join(errors))
for e in errors:
    print("ΠΡΟΣΟΧΗ (config.env):", e)
errors.clear()


def read(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return f.read().decode("utf-8").replace("\r\n", "\n")


def write(path, text):
    if CHECK_ONLY:
        return
    with open(os.path.join(ROOT, path), "wb") as f:
        f.write(text.encode("utf-8"))


def sub(path, old, new, count=1, regex=False):
    """Αντικατάσταση που ΑΠΑΙΤΕΙ ακριβώς `count` εμφανίσεις."""
    text = read(path)
    found = len(re.findall(old, text, flags=re.M)) if regex else text.count(old)
    if found != count:
        errors.append(f"{path}: βρέθηκαν {found} (αναμένονταν {count}) για: {old[:70]!r}")
        return
    text = re.sub(old, new, text, flags=re.M) if regex else text.replace(old, new)
    write(path, text)


# Idempotent: αν έχει ήδη γίνει branding, μην το ξανακάνεις
if MARK in read("src/common.rs"):
    print("Ήδη branded — τίποτα να γίνει.")
    sys.exit(0)

# 1) Δικός μας server + key (submodule hbb_common) -------------------------------
cfgrs = "libs/hbb_common/src/config.rs"
sub(cfgrs, r'^pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];$',
    f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{SERVER}"];', regex=True)
sub(cfgrs, r'^pub const RS_PUB_KEY: &str = "[^"]*";$',
    f'pub const RS_PUB_KEY: &str = "{KEY}";', regex=True)

# 2) Εμφανιζόμενο όνομα + απενεργοποίηση ελέγχου ενημερώσεων του rustdesk.com ----
#    (αλλιώς ο client προτείνει/κάνει auto-update στο ΕΠΙΣΗΜΟ RustDesk και
#     χάνεται ο server μας και το branding)
sub("src/common.rs",
    "pub fn check_software_update() {\n    if is_custom_client() {",
    "pub fn check_software_update() {\n    // PINGUINS: no update checks against rustdesk.com\n    if true || is_custom_client() {")
text = read("src/common.rs")
text += (
    f"\n// {MARK}\n"
    f'pub const PINGUINS_DISPLAY_NAME: &str = "{NAME}";\n'
    "#[inline]\n"
    "pub fn get_display_name() -> String {\n"
    "    PINGUINS_DISPLAY_NAME.to_owned()\n"
    "}\n"
)
write("src/common.rs", text)

# Μεταφράσεις: όπου λέει "RustDesk" να λέει το δικό μας όνομα
sub("src/lang.rs", "        if !crate::is_rustdesk() {\n            if s.contains(\"RustDesk\")",
    "        if true {\n            if s.contains(\"RustDesk\")")
sub("src/lang.rs", "                let app_name = crate::get_app_name();\n                if !app_name.contains(\"RustDesk\")",
    "                let app_name = crate::get_display_name();\n                if !app_name.contains(\"RustDesk\")")

# Tray tooltip
sub("src/tray.rs", "                crate::get_app_name(),\n", "                crate::get_display_name(),\n", count=2)

# Windows: uni-link μήνυμα βρίσκει το κύριο παράθυρο από τον ΤΙΤΛΟ του
sub("src/core_main.rs",
    "&crate::platform::FLUTTER_RUNNER_WIN32_WINDOW_CLASS,\n            &crate::get_app_name(),",
    "&crate::platform::FLUTTER_RUNNER_WIN32_WINDOW_CLASS,\n            &crate::get_display_name(),")

# 3) Flutter UI -----------------------------------------------------------------
sub("flutter/lib/common.dart",
    "String getWindowName({WindowType? overrideType}) {\n  final name = bind.mainGetAppNameSync();",
    f"String getWindowName({{WindowType? overrideType}}) {{\n  const name = '{NAME}';")
sub("flutter/lib/main.dart", "              : bind.mainGetAppNameSync(),", f"              : '{NAME}',")
sub("flutter/lib/desktop/widgets/tabbar_widget.dart", '                              "RustDesk",',
    f'                              "{NAME}",')
sub("flutter/lib/mobile/pages/home_page.dart", "return Text(bind.mainGetAppNameSync());", f"return Text('{NAME}');")

# Windows runner: ίδιος τίτλος με το Dart (single-instance = FindWindow με τίτλο)
sub("flutter/windows/runner/main.cpp", "  // Uri links dispatch\n",
    f'  app_name = L"{NAME}";  // PINGUINS: must match Dart getWindowName()\n  // Uri links dispatch\n')
rc = "flutter/windows/runner/Runner.rc"
sub(rc, r'VALUE "CompanyName", "[^"]*"', f'VALUE "CompanyName", "{COMPANY}"', regex=True)
sub(rc, r'VALUE "FileDescription", "[^"]*"', f'VALUE "FileDescription", "{NAME}"', regex=True)
sub(rc, r'VALUE "LegalCopyright", "[^"]*"', f'VALUE "LegalCopyright", "{COPYRIGHT}"', regex=True)
sub(rc, r'VALUE "ProductName", "[^"]*"', f'VALUE "ProductName", "{NAME}"', regex=True)

# Στοιχεία exe (librustdesk / service exe και portable packer)
for toml in ["Cargo.toml", "libs/portable/Cargo.toml"]:
    sub(toml, r'^LegalCopyright = ".*"$', f'LegalCopyright = "{COPYRIGHT}"', regex=True)
    sub(toml, r'^ProductName = ".*"$', f'ProductName = "{NAME}"', regex=True)
    sub(toml, r'^FileDescription = ".*"$', f'FileDescription = "{NAME}"', regex=True)

# Linux παράθυρο (GTK τίτλος)
sub("flutter/linux/my_application.cc", 'gtk_header_bar_set_title(header_bar, "rustdesk");',
    f'gtk_header_bar_set_title(header_bar, "{NAME}");')
sub("flutter/linux/my_application.cc", 'gtk_window_set_title(window, "rustdesk");',
    f'gtk_window_set_title(window, "{NAME}");')

# 4) Linux πακέτο ----------------------------------------------------------------
sub("res/rustdesk.desktop", "Name=RustDesk\n", f"Name={NAME}\n")
sub("res/rustdesk.desktop", "Comment=Remote Desktop\n",
    "Comment=Remote Desktop\nComment[el]=Απομακρυσμένη διαχείριση και μεταφορά αρχείων\n")
sub("res/rustdesk.desktop", "Keywords=internet;", "Keywords=pinguins;hub;pc2pc;internet;")
sub("res/rustdesk.desktop", "Name=Open a New Window\n", f"Name=Open a New Window\nName[el]=Νέο παράθυρο {NAME}\n")
sub("res/rustdesk-link.desktop", "Name=RustDesk\n", f"Name={NAME}\n")

sub("build.py", "Package: rustdesk\n",
    "Package: pinguins-hub\nProvides: rustdesk\nConflicts: rustdesk, pinguins-pc2pc\nReplaces: rustdesk, pinguins-pc2pc\n")
sub("build.py", "Maintainer: rustdesk <info@rustdesk.com>\n", f"Maintainer: {MAINTAINER}\n")
sub("build.py", "Homepage: https://rustdesk.com\n", f"Homepage: {HOMEPAGE}\n")
sub("build.py", "Description: A remote control software.\n",
    f"Description: {NAME} - remote desktop and file transfer\n {NAME} by {COMPANY}, based on RustDesk (AGPL-3.0).\n")

# 5) Εικονίδια / logo ----------------------------------------------------------
assets = os.path.join(HERE, "assets")
copied = 0
for dirpath, _, files in os.walk(assets):
    for fn in files:
        src = os.path.join(dirpath, fn)
        rel = os.path.relpath(src, assets)
        dst = os.path.join(ROOT, rel)
        if not os.path.isdir(os.path.dirname(dst)):
            errors.append(f"λείπει φάκελος προορισμού για {rel}")
            continue
        if not CHECK_ONLY:
            shutil.copyfile(src, dst)
        copied += 1
EXPECTED_ASSETS = 15  # αν λείπουν (π.χ. τα έφαγε το .gitignore), ΜΗΝ βγει client με τα εικονίδια του RustDesk
if copied != EXPECTED_ASSETS:
    errors.append(f"assets: βρέθηκαν {copied}, αναμένονταν {EXPECTED_ASSETS} — έγιναν commit όλα τα pinguins/assets;")

if errors:
    sys.exit("ΣΦΑΛΜΑ branding (το source άλλαξε; έλεγξε το tag):\n  " + "\n  ".join(errors))
print(f"{'Έλεγχος OK' if CHECK_ONLY else 'Branding OK'}: server={SERVER}, όνομα={NAME}, assets={copied}")
