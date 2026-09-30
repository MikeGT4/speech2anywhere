from __future__ import annotations
from typing import Any
import yaml


def _format_scalar(value: Any) -> str:
    text = yaml.safe_dump(value, default_flow_style=False).strip()
    if text.endswith("..."):
        text = text[:-3].strip()
    return text


def update_scalars(yaml_text: str, updates: dict[str, Any]) -> str:
    grouped: dict[str, dict[str, Any]] = {}
    for dotted, value in updates.items():
        if "." not in dotted:
            raise ValueError(f"expected 'section.key', got {dotted!r}")
        section, key = dotted.split(".", 1)
        grouped.setdefault(section, {})[key] = value

    found: set[str] = set()
    out_lines: list[str] = []
    current_section: str | None = None
    section_indent: int | None = None

    for raw_line in yaml_text.splitlines(keepends=True):
        line = raw_line.rstrip("\n")
        stripped = line.lstrip()
        leading = len(line) - len(stripped)

        if not stripped or stripped.startswith("#"):
            out_lines.append(raw_line)
            continue

        if leading == 0 and ":" in stripped:
            name = stripped.split(":", 1)[0].strip()
            current_section = name if name in grouped else None
            section_indent = None
            out_lines.append(raw_line)
            continue

        if current_section is None:
            out_lines.append(raw_line)
            continue

        if section_indent is None and leading > 0:
            section_indent = leading

        if leading == section_indent and ":" in stripped:
            key_name = stripped.split(":", 1)[0].strip()
            if key_name in grouped[current_section]:
                new_value = grouped[current_section][key_name]
                formatted = _format_scalar(new_value)
                indent = " " * leading
                tail = "\n" if raw_line.endswith("\n") else ""
                out_lines.append(f"{indent}{key_name}: {formatted}{tail}")
                found.add(f"{current_section}.{key_name}")
                continue

        if leading == 0:
            current_section = None
            section_indent = None

        out_lines.append(raw_line)

    missing = set(updates) - found
    if missing:
        original_lines = yaml_text.splitlines(keepends=True)
        out_lines = _append_missing(out_lines, updates, missing, original_lines)

    return "".join(out_lines)


def _existing_top_sections(lines: list[str]) -> set[str]:
    found: set[str] = set()
    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            leading = len(line) - len(stripped)
            if leading == 0:
                name = stripped.split(":", 1)[0].strip()
                found.add(name)
    return found


def _append_missing(
    out_lines: list[str],
    updates: dict[str, Any],
    missing: set[str],
    original_lines: list[str],
) -> list[str]:
    by_section: dict[str, dict[str, Any]] = {}
    for path in missing:
        section, key = path.split(".", 1)
        by_section.setdefault(section, {})[key] = updates[path]

    existing_sections = _existing_top_sections(original_lines)

    sections_to_insert = {
        s: kvs for s, kvs in by_section.items() if s in existing_sections
    }
    if sections_to_insert:
        out_lines = _insert_into_sections(out_lines, sections_to_insert)

    new_sections = {
        s: kvs for s, kvs in by_section.items() if s not in existing_sections
    }
    if new_sections:
        if out_lines and not out_lines[-1].endswith("\n"):
            out_lines[-1] = out_lines[-1] + "\n"
        for section, kvs in new_sections.items():
            out_lines.append(f"\n{section}:\n")
            for key, value in kvs.items():
                out_lines.append(f"  {key}: {_format_scalar(value)}\n")

    return out_lines


def _insert_into_sections(
    out_lines: list[str],
    sections_to_insert: dict[str, dict[str, Any]],
) -> list[str]:
    section_spans: dict[str, tuple[int, int]] = {}
    current_section: str | None = None
    section_start = -1
    for i, raw in enumerate(out_lines):
        line = raw.rstrip("\n")
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            leading = len(line) - len(stripped)
            if leading == 0:
                if current_section is not None:
                    section_spans[current_section] = (section_start, i)
                name = stripped.split(":", 1)[0].strip()
                if name in sections_to_insert:
                    current_section = name
                    section_start = i
                else:
                    current_section = None
                    section_start = -1
    if current_section is not None:
        section_spans[current_section] = (section_start, len(out_lines))

    inserts: list[tuple[int, list[str]]] = []
    for section, (start, end) in section_spans.items():
        insert_at = end
        while insert_at > start + 1 and out_lines[insert_at - 1].strip() == "":
            insert_at -= 1
        new_lines: list[str] = []
        for key, value in sections_to_insert[section].items():
            new_lines.append(f"  {key}: {_format_scalar(value)}\n")
        inserts.append((insert_at, new_lines))

    inserts.sort(key=lambda t: t[0], reverse=True)
    for idx, lines_to_add in inserts:
        out_lines = out_lines[:idx] + lines_to_add + out_lines[idx:]
    return out_lines
