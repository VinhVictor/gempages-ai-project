---
name: gempages-export-builder
description: Use this skill whenever the user wants to create, build, generate, repack, or modify a `.gempages` export file (the file format used by GemPages — a Shopify page builder — to export and import landing pages, theme pages, blog posts, products, collections, etc.). Trigger on any mention of `.gempages` files, "GemPages export", "gempages package", "gempages bundle", or when a user uploads a `.gempages` file and wants to inspect, modify, rebuild, or programmatically generate one. Also trigger when the user asks to convert page JSON into an importable GemPages file, or to fix the structure of a broken `.gempages` archive, or when the user wants to convert HTML (pasted or from a URL) into a `.gempages` file that can be imported into GemPages. The output is always a correctly-structured nested-ZIP archive that GemPages can re-import without errors.
---

# GemPages Export File Builder

A `.gempages` file is **not a single JSON file** — it is a nested ZIP archive with a very specific structure. Getting any layer wrong (filenames, nesting, missing manifest, mismatched IDs) will cause GemPages to reject the import. This skill encodes the exact structure derived from a real export and provides a script to build one correctly every time.

## File format (must match exactly)

A `.gempages` file is a ZIP archive. The outer ZIP contains exactly these entries:

```
<anything>.gempages                  ← outer ZIP, extension is .gempages (not .zip)
├── manifest.json                    ← plain JSON, NOT zipped
├── image_urls.txt                   ← plain text, one CDN URL per line, NOT zipped (omit if image_url_count is 0)
├── pages_info.zip                   ← inner ZIP
│   └── pages_info.json              ← list of pages contained in the export
├── 1_<pageId>.zip                   ← inner ZIP for first page
│   └── 1_<pageId>.json
└── 2_<pageId>.zip                   ← inner ZIP for second page (counter increments per page)
    └── 2_<pageId>.json
```

Critical rules:

- The outer file's extension must be `.gempages`, but it is a standard ZIP. Never gzip or tar it.
- `manifest.json` sits at the root of the outer ZIP, **not inside another zip**.
- `image_urls.txt` sits at the root of the outer ZIP, **not inside another zip**. Include it when `image_url_count > 0` in `manifest.json`; omit it otherwise.
- Each page is wrapped in its **own** inner zip. The inner zip and the JSON inside it share the same base name: `<N>_<pageId>.zip` contains exactly `<N>_<pageId>.json`. **The numeric prefix is a 1-based counter** (1 for the first page, 2 for the second, etc.) — it is NOT always `1_`.
- `pages_info.zip` always contains exactly one file named `pages_info.json`.
- The `pageId` (e.g. `618435406517502927`) is a 64-bit integer. It must be **identical** in three places: the inner zip filename, the JSON filename inside it, and the `id` field at the top of that JSON. It must also appear in `pages_info.json` and match the `theme_page_count` accounting in `manifest.json`.
- Use ZIP DEFLATE compression. Do not store uncompressed. (Standard `zipfile.ZIP_DEFLATED` in Python works.)

## Required content of each file

### `manifest.json` (top level, plain JSON)

```json
{
  "export_version": "export_v2",
  "theme_page_count": 1,
  "theme_section_count": 0,
  "image_url_count": 0,
  "shop_curr_version": 317576412
}
```

- `export_version` is `"export_v2"` for the current GemPages format.
- `theme_page_count` must equal the number of `1_<pageId>.zip` entries in the outer archive.
- `theme_section_count` and `image_url_count` are `0` for a basic page-only export.
- `shop_curr_version` is an integer; copy it from a known-good export from the same shop, or use the value from the page JSON's `globalStoreReleaseID` if available.

### `pages_info.json` (inside `pages_info.zip`)

A JSON array, one object per page:

```json
[
  {
    "id": 618435406517502927,
    "name": "Landing Page - Blank - May 7, 16:23:46",
    "type": "GP_STATIC"
  }
]
```

- `id` must be a **JSON number** (not a string), and must match the page's `id` exactly.
- `type` values seen in the wild: `GP_STATIC` (landing page), `GP_PRODUCT`, `GP_COLLECTION`, `GP_BLOG_POST`, `GP_HOME`, `GP_REGULAR`. Use the same value the source page uses.

### `1_<pageId>.json` (inside `1_<pageId>.zip`)

The full page payload. Top-level fields (only ten — everything else lives inside each `pageSection`):

| Field             | Type                     | Notes                                                                                   |
| ----------------- | ------------------------ | --------------------------------------------------------------------------------------- |
| `id`              | int64                    | Must equal the filename ID and the entry in `pages_info.json`.                          |
| `isMobile`        | bool                     | Usually `false`.                                                                        |
| `splitPercentage` | int                      | Usually `0`.                                                                            |
| `name`            | string                   | Human-readable page name; matches `pages_info.json`.                                    |
| `type`            | string                   | Matches `pages_info.json`.                                                              |
| `description`     | string                   | May be empty.                                                                           |
| `handle`          | string                   | URL slug.                                                                               |
| `sectionPosition` | array of stringified IDs | Order of `pageSections[*].id`, **as strings**.                                          |
| `meta`            | array of meta objects    | Page-level metadata (lock, global layout, SEO). May be `[]`.                            |
| `pageSections`    | array of section objects | The actual content. May be `[]` for a blank page (then `sectionPosition` is also `[]`). |

Per-section fields (`pageSections[*]`) include `display`, `isGlobal`, `appBlocks`, `globalStoreReleaseID`, `customFontIDs`, `checksum`, `edges`, etc. — see `references/page_schema.md` for the full list.

The `pageSections[*].component` field is itself a **JSON-encoded string** (not a nested object). It contains the visual builder tree (`tag`, `settings`, `styles`, `advanced`, `childrens`). When you modify it, parse → edit → re-stringify; do not leave it as a raw object.

`sectionPosition` entries are **strings** of the section IDs even though the IDs themselves are int64s elsewhere. This is intentional — match it.

For a deeper field-by-field reference (including the `component` tree, meta keys, and minimal page templates), see `references/page_schema.md`.

## How to build the file

**Always use the helper script** rather than building zips by hand — it gets the nesting, filenames, and ID consistency right and validates the output.

```bash
python3 scripts/build_gempages.py \
    --page-json path/to/page.json \
    --output path/to/result.gempages
```

The script:

1. Reads the page JSON.
2. Extracts the `id`, `name`, `type` to generate `pages_info.json`.
3. Generates `manifest.json` (using the first section's `globalStoreReleaseID` for `shop_curr_version` if available — note this field lives on `pageSections[*]`, not the page top level).
4. Wraps the page JSON in `1_<pageId>.zip`.
5. Wraps `pages_info.json` in `pages_info.zip`.
6. Combines all three into the outer `.gempages` ZIP.
7. Re-opens the result and validates the round-trip (every file extracts, IDs match, JSON parses).

There is also a multi-page mode:

```bash
python3 scripts/build_gempages.py \
    --page-json page1.json page2.json \
    --output bundle.gempages
```

And an inspect/extract mode for unpacking an existing `.gempages` for inspection:

```bash
python3 scripts/build_gempages.py --inspect path/to/file.gempages --extract-to ./out/
```

## How to modify an existing `.gempages`

1. Run `--inspect --extract-to` to unpack into a folder.
2. Edit `1_<pageId>.json` (the page data). If editing the visual tree, remember `pageSections[*].component` is a JSON string — parse, edit, re-stringify.
3. Re-build with `--page-json` pointing at the modified JSON.
4. **Do not just re-zip the extracted folder** with a generic zip command — the nested zip layout will be flattened and the import will fail.

## Common pitfalls

- **Single-zip mistake**: putting `manifest.json`, `pages_info.json`, and `<page>.json` all directly into one ZIP. Wrong — `pages_info.json` must be inside `pages_info.zip`, and each page JSON must be inside its own `<N>_<pageId>.zip`.
- **Wrong page zip prefix**: using `1_` for every page in a multi-page export. Wrong — the prefix is a 1-based counter: `1_<id>.zip`, `2_<id>.zip`, etc.
- **Missing image_urls.txt**: when `manifest.json` has `image_url_count > 0`, the `image_urls.txt` file must be present at the root of the outer ZIP (plain text, not zipped).
- **Mismatched IDs**: changing the page name but not the page ID, or vice versa, between `pages_info.json` and the page JSON. They must agree.
- **String vs number IDs**: `id` fields are numbers; `sectionPosition` entries are strings. Don't normalize them to one form.
- **Treating `component` as an object**: it's a JSON-encoded string inside the JSON. Editing it requires `JSON.parse` then `JSON.stringify`.
- **Extension**: the outer file must end in `.gempages`. Renaming a `.zip` to `.gempages` is fine — that's literally what it is — but the GemPages import UI filters by extension.
- **Compression**: use DEFLATE. STORE (uncompressed) sometimes works but is non-standard for these exports.

## When a user uploads a `.gempages` and asks for help

First, run the inspect mode to see what's inside:

```bash
python3 scripts/build_gempages.py --inspect <uploaded_file>
```

This prints the page count, IDs, names, and any structural anomalies before you touch anything. Only then propose edits.

---

## Converting HTML (or a URL) into a `.gempages` file

This workflow covers the full pipeline: raw HTML → normalized, GemPages-compliant sections → page JSON → packaged `.gempages` file ready to import.

### Overview

```
HTML input
  └─► Step 0: Extract & classify <head> resources (CSS/JS/fonts) ← MANDATORY if input has <head>
        └─► Step 1: Split HTML into sections (semantic boundaries) ← MANDATORY
              └─► Step 2: Normalize each section into compliant section envelopes
                    └─► Step 3: Build component JSON (Section → Col → CSSCode scaffold)
                          └─► Step 4: Build page JSON (pageSections + sectionPosition)
                                └─► Step 5: Package into .gempages file
```

---

### Step 0 — Extract & classify `<head>` resources ⚠️ MANDATORY (if input contains `<head>`)

GemPages sections must be **self-contained** — every section's `<style>` and `<script>` carries only the CSS/JS it actually needs. A raw HTML input typically dumps shared resources into `<head>` (global `<style>`, `<link rel="stylesheet">`, `<script src>`, font imports). These must be extracted, classified, and re-distributed into the right sections **before** Step 1 runs.

Skip this step only if the input has no `<head>` (e.g. a bare fragment with no global resources).

#### A. Inventory everything in `<head>`

Enumerate every resource and record its kind:

| Found in `<head>`                                       | Kind                                                              |
| ------------------------------------------------------- | ----------------------------------------------------------------- |
| `<style>…</style>`                                      | inline-css                                                        |
| `<link rel="stylesheet" href="…">`                      | external-css                                                      |
| `@import url(…);` inside a `<style>`                    | css-import (font or library)                                      |
| `<script>…</script>`                                    | inline-js                                                         |
| `<script src="…"></script>`                             | external-js                                                       |
| `<meta>`, `<title>`, `<link rel="icon">`, OG tags, etc. | page-meta → goes into page-level `meta`, **not** into any section |

#### B. Resolve external resources

- **External CSS link** — if it is a CDN library (Bootstrap/Tailwind/etc.), record the URL and treat it as a single `@import url(...)` to be re-emitted into the sections that need it. If it is an internal stylesheet you can fetch, inline its contents and process as inline-css.
- **External JS script** — if it is jQuery or a library that requires the DOM globally, find a vanilla replacement (R5 forbids jQuery). If it is a pure utility lib with no global side effects, keep it as `<script src="…" defer></script>` inside the section that uses it. If internal and fetchable, inline its body and process as inline-js.
- **Font `@import`** — rewrite to **Bunny Fonts** per R4 (`https://fonts.bunny.net/css?family=…&display=swap`), keep only the weights actually used.

#### C. Classify CSS rules → sections

For each parsed CSS rule, decide which section(s) it belongs to by matching the selector against the HTML of each candidate section:

```
For each CSS rule R:
  targets = parse selector(s) of R   # class names, ids, element types
  matched_sections = [S for S in candidate_sections if HTML(S) contains any target]

  if R is a reset/base rule (*, html, body, ::before, ::after, :root vars):
      → duplicate into EVERY section (becomes part of R9 scoped reset)
  elif len(matched_sections) == 0:
      → DROP (dead CSS); log a warning
  elif len(matched_sections) == 1:
      → emit into that section's <style>
  else:
      → DUPLICATE into each matched section's <style>
```

Special cases:

- `@font-face` and `@import` for fonts → duplicate into every section that uses the font-family.
- `@keyframes` → duplicate into every section that references the animation name.
- CSS custom properties on `:root` → duplicate into every section that references the variables (or, simpler, into all sections).

#### D. Classify JS blocks → sections

For each parsed JS block, find the DOM references and map to sections:

```
For each JS block J:
  dom_refs = extract refs: querySelector('…'), getElementById('…'),
             getElementsByClassName('…'), class/id string literals,
             addEventListener targets
  matched_sections = [S for S in candidate_sections if HTML(S) contains any ref]

  if J has no DOM refs (pure utility / polyfill):
      → duplicate into every section that calls its exported functions
        (or every section, if usage is unclear)
  elif len(matched_sections) == 0:
      → DROP (dead JS); log a warning
  else:
      → emit into each matched section's <script>, wrapped per R5 (IIFE + root guard)
```

After classification, every JS block must be wrapped in the section's IIFE — never leave top-level `var`/`let`/`const`, never rely on cross-section globals (each IIFE is isolated).

#### E. Produce the per-section bundle

Output of Step 0 is, for each prospective section, a triple:

```
section_id → {
  css:    "<all CSS rules assigned to this section, including @imports and reset>",
  js:     "<all JS assigned to this section, raw — wrapping into IIFE happens in Step 2 R5>",
  html:   "<the HTML fragment of this section, still with original class names>"
}
```

This bundle becomes the input to Step 1 (which may further split a section if it exceeds the 200 KB component-size limit) and Step 2 (which applies R1–R9 normalization).

#### F. Distribution rules cheat-sheet

| Resource                       | Destination                                       |
| ------------------------------ | ------------------------------------------------- |
| Font `@import` (Bunny Fonts)   | Every section using the font-family               |
| Reset / base / `:root` vars    | **All** sections (becomes R9 scoped reset)        |
| CSS rule matching 1 section    | That section only                                 |
| CSS rule matching N sections   | Duplicated into each                              |
| CSS rule matching 0 sections   | Dropped (with warning)                            |
| `@keyframes`                   | Every section referencing the animation           |
| JS event listener / DOM logic  | Section containing the target element             |
| JS utility function            | Section(s) that call it (duplicate if multiple)   |
| External CDN CSS library       | `@import` in each section using it                |
| External CDN JS library        | `<script src="…" defer>` in each section using it |
| Page-meta (title, OG, favicon) | Page-level `meta` array, **not** in any section   |

#### G. Invariants to verify before leaving Step 0

- [ ] Every CSS rule from `<head>` is either assigned to ≥1 section or explicitly dropped.
- [ ] Every JS block from `<head>` is either assigned to ≥1 section or explicitly dropped.
- [ ] No section depends on a global `<head>` resource that has not been duplicated into it.
- [ ] All font imports have been rewritten to Bunny Fonts (R4).
- [ ] All `<link>` and `<script src>` that survive are either Bunny Fonts `@import` or `defer`-loaded pure libraries.
- [ ] Class names are still in their original form (gp- prefixing happens in Step 2 R2, not here).

### Step 1 — Split HTML into sections ⚠️ MANDATORY

**This step is required for every HTML-to-GemPages conversion, without exception.** Before any normalization or component building, always analyze the full HTML input and explicitly identify its semantic sections.

The result may be one section or many — both are valid. What is not valid is skipping this analysis and treating the entire HTML as one blob by default.

Rules:

- Each distinct content block → one section: **Hero, Features, Testimonials, FAQ, CTA, Footer**, etc.
- If the input genuinely contains only one semantic block, the output of this step is one section — no artificial splitting required.
- Never split mid-block just to reduce size.
- Never merge unrelated blocks into one section to simplify.
- Hard size constraint: each serialized `component` JSON string must stay under **200 KB** (~150 KB of HTML/CSS/JS is safe headroom). If a semantically single block exceeds 200 KB, split at the next natural sub-boundary and note the reason.

**Output of this step:** a numbered list of section blocks, each with a clear label (e.g. `Section 1 — Hero`, `Section 2 — Features`, …). Only then proceed to Step 2 for each block individually.

---

### Step 2 — Normalize each section into compliant section envelopes

Before converting to a `.gempages` component, every HTML block must be normalized. Apply these rules in order; auto-fix everything possible and report violations found.

**R1 — Self-contained section envelope**
Wrap each semantic block (Hero, Features, FAQ, CTA, Footer, etc.) in:

```html
<div aria-label="<section purpose>">
  <style>
    /* CSS here */
  </style>
  <!-- HTML / Liquid content (no inline styles) -->
  <script>
    /* JS here */
  </script>
</div>
```

All three child tags must be present even when empty.

**R2 — CSS scoping (`gp-` prefix + rootClassName)**
Every CSS class must use a `gp-` prefix and every selector must be scoped under `.{{rootClassName}}`:

```css
/* ❌ bare */
.hero { max-width: 1200px; }
/* ✅ correct */
.{{rootClassName}} .gp-hero { max-width: 1200px; }
@media (min-width: 768px) { .{{rootClassName}} .gp-grid { gap: 32px; } }
```

HTML attributes update to match: `<div class="gp-hero">`.

**R3 — No `!important`** — increase selector specificity instead.

**Exception for GemPages framework conflicts:** GemPages applies `max-width: 100%` to all descendants via a utility class with specificity 0,2,0. Only `max-width` (and `width` if needed) on constrained elements may use `!important` as the last resort. Do not blanket `!important` everything.

**R4 — Font imports (per section)**
Use Bunny Fonts (GDPR-friendly), import only used weights, always append `&display=swap`:

```css
@import url("https://fonts.bunny.net/css?family=inter:400,700&display=swap");
```

Fallback stack always required: `font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;`
Prefer theme CSS variables: `font-family: var(--font-heading-family, 'Inter', sans-serif);`

**R5 — JS isolation (IIFE + root guard)**

```js
(function () {
  var root = document.querySelector(".{{rootClassName}}");
  if (!root) return;
  // all logic here
})();
```

No top-level `var`/`let`/`const`. No jQuery. Async external scripts: `<script src="..." defer></script>`.

**R6 — Responsive: mobile-first**
Base styles target mobile; enhancements via `min-width` media queries:

```css
.{{rootClassName}} .gp-grid { display: flex; flex-direction: column; }
@media (min-width: 768px)  { .{{rootClassName}} .gp-grid { flex-direction: row; } }
@media (min-width: 1024px) { .{{rootClassName}} .gp-grid { gap: 48px; } }
```

**R7 — Semantic HTML structure**
One `<h1>` per page (hero only). `<h2>` for section headings, `<h3>` for sub-items. `aria-label` on every section envelope (the outer `<div>` per R1). Use real semantic tags (`<nav>`, `<header>`, `<footer>`, `<article>`, `<figure>`, `<figcaption>`, `<ul>/<ol>/<li>`, `<button>`, `<a>`) only when their semantics actually match. Do **not** use `<section>` as the envelope — see R10.

**R8 — Images: lazy loading + dimensions**

```html
<!-- Hero/LCP -->
<img
  src="..."
  alt="..."
  loading="eager"
  fetchpriority="high"
  width="1200"
  height="600"
/>
<!-- All others -->
<img src="..." alt="..." loading="lazy" width="800" height="600" />
```

**R9 — Scoped CSS reset per section (critical for Shopify themes)**
The custom code renders inside GemPages' framework on a Shopify theme. Always include a scoped reset:

```css
.{{rootClassName}} *,
.{{rootClassName}} *::before,
.{{rootClassName}} *::after { margin:0; padding:0; box-sizing:border-box; }
.{{rootClassName}} { line-height:1.7; font-size:16px; }
```

**R10 — HTML must not contain `<section>`**
The envelope is already a `<div>` (R1) and the GemPages framework wraps the output in its own `Section` component (Step 3). Adding any `<section>` tag inside the section's HTML creates a redundant / nested landmark. Strip every `<section>` (opening and closing) from the HTML and replace it with `<div>`; preserve `aria-label`, `id`, and other attributes on the new `<div>`.

```html
<!-- ❌ -->
<section class="hero" aria-label="Hero">…</section>
<!-- ✅ -->
<div class="gp-hero" aria-label="Hero">…</div>
```

**R11 — Strip `shopify-section` and `gps-lazy`**
Remove any `class` or `id` token that contains `shopify-section` or `gps-lazy` (including suffixed variants like `shopify-section-template--xxx` or `gps-lazy-loaded`). If the attribute becomes empty after removal, drop the attribute entirely.

After normalization, extract from the envelope:

- `html` — content between `</style>` and `<script>`
- `css` — full contents of `<style>` block (including `@import`)
- `javascript` — full contents of `<script>` block

---

### Step 3 — Build component JSON (Section → Col → CSSCode scaffold)

**The only three valid tag values are:** `"Section"`, `"Col"`, `"CSSCode"` — exactly as written (case-sensitive). No other tags (`Container`, `Row`, `Block`, `HTML`, `Div`, etc.) are valid.

Generate random 8–10 char alphanumeric UIDs for each node (e.g. `g_EQ5APigL`).

The `html`, `css`, `javascript` extracted in Step 1 go into `advanced.editorData` of the `CSSCode` leaf — **nowhere else**.

```json
{
  "uid": "<uid-A>",
  "tag": "Section",
  "label": "Section",
  "settings": {
    "layout": { "desktop": { "cols": [12], "display": "fill" } },
    "horizontalAlign": { "desktop": "start" },
    "verticalAlign": { "desktop": "start" },
    "lazy": false
  },
  "styles": {
    "verticalGutter": { "desktop": "32px" },
    "background": {
      "desktop": {
        "type": "color",
        "color": "transparent",
        "image": { "src": "", "width": 0, "height": 0 },
        "size": "cover",
        "position": { "x": 50, "y": 50 },
        "repeat": "no-repeat",
        "attachment": "scroll"
      }
    },
    "preloadBgImage": false,
    "width": { "desktop": "100%" }
  },
  "advanced": {
    "spacing-setting": {
      "edited": ["desktop"],
      "desktop": {
        "padding": { "top": "0px", "bottom": "0px" },
        "link": false
      },
      "tablet": { "padding": { "top": "0px", "bottom": "0px" } },
      "mobile": { "padding": { "top": "0px", "bottom": "0px" } }
    },
    "d": { "desktop": true, "tablet": true, "mobile": true },
    "border": {
      "desktop": {
        "normal": {
          "borderType": "none",
          "border": "solid",
          "borderWidth": "0px",
          "width": "0px",
          "color": "#121212",
          "isCustom": true
        }
      }
    },
    "rounded": {
      "desktop": {
        "normal": {
          "btrr": "0px",
          "bblr": "0px",
          "bbrr": "0px",
          "btlr": "0px",
          "radiusType": "none"
        }
      }
    },
    "hasBoxShadow": { "desktop": { "normal": false } },
    "boxShadow": {
      "desktop": {
        "normal": {
          "type": "shadow-1",
          "distance": "4px",
          "blur": "12px",
          "spread": "0px",
          "color": "rgba(0,0,0,0.20)",
          "angle": 90
        }
      }
    },
    "op": { "desktop": "100%" }
  },
  "childrens": [
    {
      "uid": "<uid-B>",
      "tag": "Col",
      "label": "Block",
      "settings": {},
      "styles": {},
      "advanced": {
        "d": { "desktop": true, "tablet": true, "mobile": true },
        "border": {
          "desktop": {
            "normal": {
              "borderType": "none",
              "border": "solid",
              "borderWidth": "0px",
              "width": "0px",
              "color": "#121212",
              "isCustom": true
            }
          }
        },
        "rounded": {
          "desktop": {
            "normal": {
              "btrr": "0px",
              "bblr": "0px",
              "bbrr": "0px",
              "btlr": "0px",
              "radiusType": "none"
            }
          }
        },
        "hasBoxShadow": { "desktop": { "normal": false } },
        "boxShadow": {
          "desktop": {
            "normal": {
              "type": "shadow-1",
              "distance": "4px",
              "blur": "12px",
              "spread": "0px",
              "color": "rgba(0,0,0,0.20)",
              "angle": 90
            }
          }
        },
        "op": { "desktop": "100%" }
      },
      "childrens": [
        {
          "uid": "<uid-C>",
          "tag": "CSSCode",
          "label": "Custom Code",
          "customLabel": "Custom Code",
          "settings": {
            "editorData": { "customLabel": "Custom Code" },
            "customLabel": "Custom code",
            "background": {
              "desktop": {
                "type": "color",
                "color": "transparent",
                "image": { "src": "", "width": 0, "height": 0 },
                "size": "cover",
                "position": { "x": 50, "y": 50 },
                "repeat": "no-repeat",
                "attachment": "scroll"
              }
            },
            "align": { "desktop": "left" }
          },
          "styles": {},
          "advanced": {
            "d": { "desktop": true, "tablet": true, "mobile": true },
            "border": {
              "desktop": {
                "normal": {
                  "borderType": "none",
                  "border": "none",
                  "borderWidth": "1px",
                  "width": "1px 1px 1px 1px",
                  "color": "line-3",
                  "isCustom": true
                }
              }
            },
            "rounded": {
              "desktop": {
                "normal": {
                  "btrr": "0px",
                  "bblr": "0px",
                  "bbrr": "0px",
                  "btlr": "0px",
                  "radiusType": "none"
                }
              }
            },
            "hasBoxShadow": { "desktop": { "normal": false } },
            "boxShadow": { "desktop": { "normal": {} } },
            "op": { "desktop": "100%" },
            "spacing-setting": { "desktop": { "margin": { "bottom": 0 } } },
            "editorData": {
              "customLabel": "Custom Code",
              "rootClassName": "{{rootClassName}}",
              "html": "<PASTE LIQUID/HTML HERE>",
              "css": "<PASTE CSS HERE>",
              "javascript": "<PASTE JS HERE>"
            }
          }
        }
      ]
    }
  ]
}
```

After filling `html`, `css`, `javascript`, serialize the **object** (not an array) with `JSON.stringify()`. The result is the value for `pageSections[*].component` — a JSON-encoded string, not a nested object.

**`rootClassName` substitution:** The string `{{rootClassName}}` in the component JSON is a placeholder. GemPages substitutes it with a real class at runtime (e.g. `gp-css-code-g_EQ5APigL`). Leave `{{rootClassName}}` literal in the stored JSON — do not pre-compute it.

---

### Step 4 — Build the page JSON

Each section from Step 2 becomes one entry in `pageSections`. Assign a unique int64 `id` per section (generate a random 18-digit integer or use a timestamp-based value). The page itself also needs a unique int64 `id`.

**Full `pageSections` entry (all fields required — wrong types will cause import failure):**

```json
{
  "id": 618435421130458063,
  "createdAt": "2026-05-07T09:23:55.936354Z",
  "updatedAt": "2026-05-07T09:23:55.936355Z",
  "deletedAt": null,
  "shopId": 0,
  "themePageID": 618435406517502927,
  "cid": "gEwB5v2sff",
  "name": "Section hero-banner",
  "display": true,
  "isGlobal": false,
  "isMobile": false,
  "appBlocks": "",
  "libraryPosition": null,
  "librarySectionID": null,
  "elementNames": "CSSCode",
  "globalStoreReleaseID": 317576412,
  "customFontIDs": null,
  "checksum": "<sha256-hex of component string>",
  "layoutColumns": null,
  "layoutRows": null,
  "edges": {},
  "component": "<JSON.stringify result from Step 2>"
}
```

**Field notes — pay close attention to types:**

| Field                     | Type                  | Notes                                                                                                        |
| ------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------ |
| `id`                      | int64                 | Unique per section. Use random 18-digit integer.                                                             |
| `createdAt` / `updatedAt` | string (ISO 8601 UTC) | Use current datetime. Format: `"2026-05-07T09:23:55.936354Z"`                                                |
| `deletedAt`               | null                  | Always `null` for active sections.                                                                           |
| `shopId`                  | int64                 | Shop's numeric ID. Use `0` if unknown (safe for import).                                                     |
| `themePageID`             | int64                 | Must equal the parent page's `id`.                                                                           |
| `cid`                     | string                | Random 10-char alphanumeric (e.g. `"gEwB5v2sff"`).                                                           |
| `name`                    | string                | Human-readable section name (≤ 25 chars, kebab or space).                                                    |
| `display`                 | bool                  | `true` to show the section.                                                                                  |
| `isGlobal`                | bool                  | `false` for page-specific sections.                                                                          |
| `isMobile`                | bool                  | `false` for standard sections.                                                                               |
| `appBlocks`               | **string**            | Empty string `""` — **NOT** an array `[]`.                                                                   |
| `libraryPosition`         | null                  | Always `null` for non-library sections.                                                                      |
| `librarySectionID`        | null                  | Always `null` for non-library sections.                                                                      |
| `elementNames`            | string                | Leaf tag name, e.g. `"CSSCode"`.                                                                             |
| `globalStoreReleaseID`    | int64                 | Shop version integer. Use `317576412` if unknown.                                                            |
| `customFontIDs`           | **null**              | Always `null` — **NOT** an empty array `[]`.                                                                 |
| `checksum`                | string                | SHA-256 hex digest of the `component` string. Compute with `hashlib.sha256(component.encode()).hexdigest()`. |
| `layoutColumns`           | null                  | Always `null`.                                                                                               |
| `layoutRows`              | null                  | Always `null`.                                                                                               |
| `edges`                   | **object**            | Empty object `{}` — **NOT** an array `[]`.                                                                   |
| `component`               | string                | JSON.stringify of the Section→Col→CSSCode tree from Step 2.                                                  |

**Critical type traps (will silently break import):**

- `appBlocks` must be `""` not `[]`
- `customFontIDs` must be `null` not `[]`
- `edges` must be `{}` not `[]`
- `checksum` must be SHA-256 hex of the component string, not empty string

**Python helper to build a correct section entry:**

```python
import hashlib, secrets, datetime

def cid():
    """Random 10-char alphanumeric cid."""
    alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def make_section(section_id, page_id, name, component_str, shop_id=0, store_release_id=317576412):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
    checksum = hashlib.sha256(component_str.encode('utf-8')).hexdigest()
    return {
        "id": section_id,
        "createdAt": now,
        "updatedAt": now,
        "deletedAt": None,
        "shopId": shop_id,
        "themePageID": page_id,
        "cid": cid(),
        "name": name,
        "display": True,
        "isGlobal": False,
        "isMobile": False,
        "appBlocks": "",
        "libraryPosition": None,
        "librarySectionID": None,
        "elementNames": "CSSCode",
        "globalStoreReleaseID": store_release_id,
        "customFontIDs": None,
        "checksum": checksum,
        "layoutColumns": None,
        "layoutRows": None,
        "edges": {},
        "component": component_str
    }
```

- `component` is a JSON-encoded string (output of `JSON.stringify` on the Section object from Step 2).
- `globalStoreReleaseID` — use the shop's current version integer if known; otherwise use `317576412` as a safe default.
- `checksum` — SHA-256 hex digest of the `component` string. **Do not leave empty.**
- `edges` — empty object `{}` (not array).

The full page object (top-level, 10 fields):

```json
{
  "id": 618435406517502927,
  "isMobile": false,
  "splitPercentage": 0,
  "name": "Page Name",
  "type": "GP_STATIC",
  "description": "",
  "handle": "page-handle",
  "sectionPosition": ["618435406517502928"],
  "meta": [],
  "pageSections": [
    /* section objects */
  ]
}
```

- `sectionPosition` entries are **strings** of the section IDs (even though the IDs are int64s elsewhere).
- `type` values: `GP_STATIC` (landing page), `GP_PRODUCT`, `GP_COLLECTION`, `GP_BLOG_POST`, `GP_HOME`, `GP_REGULAR`.

---

### Step 5 — Package into `.gempages` file

Use `build_gempages.py` to package:

```bash
python3 scripts/build_gempages.py \
    --page-json path/to/page.json \
    --output result.gempages
```

For multi-section pages: all sections go inside one `page.json`; each is an element of `pageSections`, and all section IDs (as strings) go into `sectionPosition` in render order.

For multi-page exports:

```bash
python3 scripts/build_gempages.py \
    --page-json page1.json page2.json \
    --output bundle.gempages
```

---

### Validation checklist before packaging

Before running `build_gempages.py`, verify each section:

```
SECTION: <section-name>
─────────────────────────────────────────
✅ R1   Section envelope: <div aria-label="…"><style>…</style> CONTENT <script>…</script></div>
✅ R2   All CSS classes gp- prefixed + scoped under .{{rootClassName}}
✅ R3   No !important (except max-width on constrained elements)
✅ R4   Font imports (Bunny Fonts, only used weights, &display=swap)
✅ R5   JS wrapped in IIFE with root guard, no jQuery
✅ R6   Mobile-first responsive breakpoints (min-width only)
✅ R7   Semantic HTML (h2 section headings, aria-label on envelope <div>)
✅ R8   Images: loading="lazy" + width/height; hero: loading="eager" fetchpriority="high"
✅ R9   Scoped CSS reset present
✅ R10  HTML contains no <section> tags (replaced with <div>; aria-label preserved)
✅ R11  No class/id contains "shopify-section" or "gps-lazy" (empty attributes removed)
✅ Component: tag = "Section" → "Col" → "CSSCode" (exact case)
✅ Component: html/css/javascript in advanced.editorData of CSSCode leaf only
✅ Component: JSON.stringify'd into a string (not nested object)
✅ Page JSON: sectionPosition entries are strings, not numbers
✅ Page JSON: id is a 64-bit integer, unique
```

---

### Full example: single-section HTML page

Given input HTML:

```html
<div class="hero">
  <h1>Welcome</h1>
  <p>Shop our collection</p>
  <a href="/collections/all">Shop Now</a>
</div>
<style>
  .hero {
    background: #fff;
    padding: 80px 20px;
    text-align: center;
  }
  .hero h1 {
    font-size: 48px;
  }
</style>
```

**Step 1 (Split):** Identify semantic blocks — this HTML is a single Hero block, so result is one section: `Section 1 — Hero`.

**Step 2 (Normalize):**

- `html`: `<section aria-label="Hero"><div class="gp-hero">...</div></section>` (simplified)
- `css`: `@import url('...');\n.{{rootClassName}} *{...}\n.{{rootClassName}} .gp-hero {...}`
- `javascript`: `(function(){ var root=...; if(!root) return; })();`

**Step 3:** Build Section→Col→CSSCode object, fill `editorData`, `JSON.stringify()` → component string.

**Step 4:** Build page JSON with one `pageSections` entry, `sectionPosition: ["<sectionId>"]`.

**Step 5:** `python3 scripts/build_gempages.py --page-json page.json --output result.gempages`
