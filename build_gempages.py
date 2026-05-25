#!/usr/bin/env python3
"""
Build, inspect, and validate `.gempages` export files.

A `.gempages` file is a nested ZIP archive with this exact structure:

    <name>.gempages           (outer ZIP)
    ├── manifest.json         (plain JSON at root)
    ├── pages_info.zip        (inner ZIP)
    │   └── pages_info.json
    └── 1_<pageId>.zip        (one per page; filename uses page ID)
        └── 1_<pageId>.json

Usage
-----
Build a single-page export:
    python3 build_gempages.py --page-json page.json --output out.gempages

Build a multi-page export:
    python3 build_gempages.py --page-json p1.json p2.json --output out.gempages

Inspect an existing .gempages:
    python3 build_gempages.py --inspect file.gempages
    python3 build_gempages.py --inspect file.gempages --extract-to ./out/
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def _collect_image_urls(obj: Any, result: list[str]) -> None:
    """Recursively walk a page section dict/list and collect image URLs."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("src", "url", "image") and isinstance(v, str) and v.startswith("http"):
                result.append(v)
            else:
                _collect_image_urls(v, result)
    elif isinstance(obj, list):
        for item in obj:
            _collect_image_urls(item, result)


def _zip_single_file(filename_inside: str, content: bytes) -> bytes:
    """Return the bytes of a ZIP archive containing one file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename_inside, content)
    return buf.getvalue()


def _load_page_json(path: Path) -> dict[str, Any]:
    """Load and minimally validate a page JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: not valid JSON ({e})") from e

    required = ["id", "name", "type"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(
            f"{path}: page JSON is missing required top-level fields: {missing}"
        )

    if not isinstance(data["id"], int):
        raise ValueError(
            f"{path}: page 'id' must be an integer (got {type(data['id']).__name__})"
        )

    return data


def build_gempages(page_json_paths: list[Path], output_path: Path) -> None:
    """Build a .gempages file from one or more page JSON files."""
    if not page_json_paths:
        raise ValueError("Need at least one page JSON file.")

    pages = [_load_page_json(p) for p in page_json_paths]

    # GemPages uses compact JSON (no spaces after `:` or `,`). Match that.
    compact = (",", ":")

    # 1. pages_info.json — array of {id, name, type} for every page
    pages_info = [
        {"id": p["id"], "name": p["name"], "type": p["type"]}
        for p in pages
    ]
    pages_info_bytes = json.dumps(pages_info, ensure_ascii=False, separators=compact).encode("utf-8") + b"\n"
    pages_info_zip = _zip_single_file("pages_info.json", pages_info_bytes)

    # 2. manifest.json — accounting + version metadata
    # `globalStoreReleaseID` lives on each pageSection (not at the page top level).
    # Pull it from the first section of the first page if available.
    shop_curr_version = 0
    first_sections = pages[0].get("pageSections") or []
    if first_sections:
        candidate = first_sections[0].get("globalStoreReleaseID")
        if isinstance(candidate, int):
            shop_curr_version = candidate

    manifest = {
        "export_version": "export_v2",
        "theme_page_count": len(pages),
        "theme_section_count": 0,
        "image_url_count": 0,
        "shop_curr_version": shop_curr_version,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, separators=compact).encode("utf-8") + b"\n"

    # 3. one inner ZIP per page: <N>_<pageId>.zip → <N>_<pageId>.json
    #    The numeric prefix is a 1-based counter, NOT always "1_".
    page_entries: list[tuple[str, bytes]] = []
    for idx, page in enumerate(pages, start=1):
        pid = page["id"]
        inner_name = f"{idx}_{pid}.json"
        outer_name = f"{idx}_{pid}.zip"
        page_bytes = json.dumps(page, ensure_ascii=False, separators=compact).encode("utf-8") + b"\n"
        page_entries.append((outer_name, _zip_single_file(inner_name, page_bytes)))

    # 4. image_urls.txt — collect all image URLs referenced in pageSections
    image_urls: list[str] = []
    for page in pages:
        for section in page.get("pageSections") or []:
            _collect_image_urls(section, image_urls)
    # deduplicate while preserving order
    seen: set[str] = set()
    unique_urls = [u for u in image_urls if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]

    # Update manifest image_url_count to match actual URLs found
    manifest["image_url_count"] = len(unique_urls)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, separators=compact).encode("utf-8") + b"\n"

    # 5. assemble outer ZIP
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as outer:
        # Order matches what the reference export uses: page zip(s), manifest, pages_info, image_urls.
        for name, data in page_entries:
            outer.writestr(name, data)
        outer.writestr("manifest.json", manifest_bytes)
        outer.writestr("pages_info.zip", pages_info_zip)
        if unique_urls:
            outer.writestr("image_urls.txt", "\n".join(unique_urls) + "\n")

    # 5. round-trip validation
    _validate(output_path, expected_page_ids=[p["id"] for p in pages])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(path: Path, expected_page_ids: list[int]) -> None:
    """Re-open the produced file and confirm structure + ID consistency."""
    with zipfile.ZipFile(path, "r") as outer:
        names = set(outer.namelist())

        if "manifest.json" not in names:
            raise RuntimeError("Validation failed: manifest.json missing from outer zip.")
        if "pages_info.zip" not in names:
            raise RuntimeError("Validation failed: pages_info.zip missing from outer zip.")

        manifest = json.loads(outer.read("manifest.json"))
        if manifest.get("theme_page_count") != len(expected_page_ids):
            raise RuntimeError(
                f"Validation failed: manifest.theme_page_count="
                f"{manifest.get('theme_page_count')} but built {len(expected_page_ids)} pages."
            )

        # pages_info.zip → pages_info.json
        with zipfile.ZipFile(io.BytesIO(outer.read("pages_info.zip"))) as info_zip:
            if "pages_info.json" not in info_zip.namelist():
                raise RuntimeError(
                    "Validation failed: pages_info.json missing inside pages_info.zip."
                )
            pages_info = json.loads(info_zip.read("pages_info.json"))

        info_ids = sorted(int(p["id"]) for p in pages_info)
        if info_ids != sorted(expected_page_ids):
            raise RuntimeError(
                f"Validation failed: pages_info IDs {info_ids} != expected {sorted(expected_page_ids)}."
            )

        # each <N>_<pid>.zip → <N>_<pid>.json with matching id field
        # The counter prefix is 1-based; find the zip by scanning outer entries.
        for idx, pid in enumerate(expected_page_ids, start=1):
            outer_name = f"{idx}_{pid}.zip"
            inner_name = f"{idx}_{pid}.json"
            if outer_name not in names:
                raise RuntimeError(f"Validation failed: {outer_name} missing.")
            with zipfile.ZipFile(io.BytesIO(outer.read(outer_name))) as page_zip:
                if inner_name not in page_zip.namelist():
                    raise RuntimeError(
                        f"Validation failed: {inner_name} missing inside {outer_name}."
                    )
                page = json.loads(page_zip.read(inner_name))
                if int(page.get("id", -1)) != pid:
                    raise RuntimeError(
                        f"Validation failed: {inner_name} has id={page.get('id')}, "
                        f"expected {pid}."
                    )


# ---------------------------------------------------------------------------
# Inspect / extract
# ---------------------------------------------------------------------------

def inspect(path: Path, extract_to: Path | None = None) -> dict[str, Any]:
    """Print and optionally extract the contents of a .gempages file."""
    summary: dict[str, Any] = {"path": str(path), "pages": [], "warnings": []}

    with zipfile.ZipFile(path, "r") as outer:
        outer_names = outer.namelist()
        summary["outer_entries"] = outer_names

        if "manifest.json" in outer_names:
            summary["manifest"] = json.loads(outer.read("manifest.json"))
        else:
            summary["warnings"].append("manifest.json missing at root")

        if "pages_info.zip" in outer_names:
            with zipfile.ZipFile(io.BytesIO(outer.read("pages_info.zip"))) as iz:
                if "pages_info.json" in iz.namelist():
                    summary["pages_info"] = json.loads(iz.read("pages_info.json"))
                else:
                    summary["warnings"].append("pages_info.json missing inside pages_info.zip")
        else:
            summary["warnings"].append("pages_info.zip missing at root")

        import re as _re
        for name in outer_names:
            # Page zips are named <counter>_<pageId>.zip where counter is a digit
            m = _re.match(r'^(\d+)_(\d+)\.zip$', name)
            if m:
                counter, pid_str = m.group(1), m.group(2)
                with zipfile.ZipFile(io.BytesIO(outer.read(name))) as pz:
                    inner_name = f"{counter}_{pid_str}.json"
                    if inner_name in pz.namelist():
                        page = json.loads(pz.read(inner_name))
                        summary["pages"].append({
                            "outer_zip": name,
                            "inner_json": inner_name,
                            "id": page.get("id"),
                            "name": page.get("name"),
                            "type": page.get("type"),
                            "handle": page.get("handle"),
                            "section_count": len(page.get("pageSections") or []),
                        })
                        if str(page.get("id")) != pid_str:
                            summary["warnings"].append(
                                f"{name}: id mismatch (filename {pid_str}, json {page.get('id')})"
                            )
                    else:
                        summary["warnings"].append(
                            f"{name}: expected {inner_name} inside, but it's missing"
                        )

        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=True)
            for name in outer_names:
                data = outer.read(name)
                if name.endswith(".zip"):
                    sub_dir = extract_to / Path(name).stem
                    sub_dir.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(io.BytesIO(data)) as iz:
                        iz.extractall(sub_dir)
                else:
                    (extract_to / name).write_bytes(data)
            summary["extracted_to"] = str(extract_to)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(summary: dict[str, Any]) -> None:
    print(f"File: {summary['path']}")
    print(f"Outer entries: {summary['outer_entries']}")
    if "manifest" in summary:
        print(f"Manifest: {summary['manifest']}")
    if "pages_info" in summary:
        print(f"pages_info ({len(summary['pages_info'])} entries):")
        for p in summary["pages_info"]:
            print(f"  - id={p.get('id')} name={p.get('name')!r} type={p.get('type')}")
    print(f"Pages ({len(summary['pages'])}):")
    for p in summary["pages"]:
        print(
            f"  - {p['outer_zip']} → {p['inner_json']}: "
            f"id={p['id']} type={p['type']} handle={p['handle']!r} "
            f"sections={p['section_count']}"
        )
    if summary["warnings"]:
        print("Warnings:")
        for w in summary["warnings"]:
            print(f"  ! {w}")
    else:
        print("Warnings: none")
    if "extracted_to" in summary:
        print(f"Extracted to: {summary['extracted_to']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--page-json", nargs="+", type=Path, help="One or more page JSON files to bundle.")
    parser.add_argument("--output", type=Path, help="Output .gempages path.")
    parser.add_argument("--inspect", type=Path, help="Inspect an existing .gempages file.")
    parser.add_argument("--extract-to", type=Path, help="When inspecting, extract contents to this directory.")
    args = parser.parse_args(argv)

    if args.inspect:
        summary = inspect(args.inspect, extract_to=args.extract_to)
        _print_summary(summary)
        return 0

    if not args.page_json or not args.output:
        parser.error("Building requires both --page-json and --output (or use --inspect).")

    build_gempages(args.page_json, args.output)
    print(f"Built {args.output} from {len(args.page_json)} page(s); validation OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
