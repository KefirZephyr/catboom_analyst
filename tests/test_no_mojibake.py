from pathlib import Path


TEXT_FILE_SUFFIXES = {".py", ".md", ".bat", ".ps1"}
SPECIAL_TEXT_FILES = {".env.example"}
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}
MOJIBAKE_PATTERNS = [
    "\u0420\u045f",
    "\u0420\u00b0",
    "\u0420\u0405",
    "\u0421\u201a",
    "\u0421\u0453",
    "\u0421\u040a",
    "\u0440\u045f",
    "\u0432\u0402",
    "\u0420\u0454",
    "\u0421\u040c",
    "\u0421\u201e",
]


def iter_project_text_files():
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.name in SPECIAL_TEXT_FILES or path.suffix in TEXT_FILE_SUFFIXES:
            yield path


def test_project_text_files_are_utf8_without_bom_and_no_mojibake():
    offenders = []
    for path in iter_project_text_files():
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            offenders.append(f"{path}: UTF-8 BOM")
            continue

        text = data.decode("utf-8")
        hits = [pattern for pattern in MOJIBAKE_PATTERNS if pattern in text]
        if hits:
            escaped = ", ".join(pattern.encode("unicode_escape").decode() for pattern in hits)
            offenders.append(f"{path}: {escaped}")

    assert not offenders, "Mojibake or BOM found:\n" + "\n".join(offenders)
