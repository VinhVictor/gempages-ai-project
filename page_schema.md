# Page JSON Schema Reference

This is the schema of the `1_<pageId>.json` file that lives inside `1_<pageId>.zip` inside a `.gempages` archive. Read this file when you need to programmatically generate or modify page content beyond just rebuilding the archive structure.

## Top-level page fields (only 10!)

The page JSON has a **flat, small** top level. Everything else lives inside `pageSections`.

| Field | Type | Notes |
|---|---|---|
| `id` | int64 | Page ID. Must match the filename and `pages_info.json`. |
| `isMobile` | bool | Mobile-specific layout flag. Almost always `false`. |
| `splitPercentage` | int | Almost always `0`. |
| `name` | string | Human-readable name. Must match `pages_info.json`. |
| `type` | string | `GP_STATIC`, `GP_PRODUCT`, `GP_COLLECTION`, `GP_BLOG_POST`, `GP_HOME`, or `GP_REGULAR`. Must match `pages_info.json`. |
| `description` | string | May be `""`. |
| `handle` | string | URL slug, lowercase-kebab-case. |
| `sectionPosition` | array of strings | Render order of `pageSections` by ID, **stringified**. Example: `["618435421130458063"]`. |
| `meta` | array of meta objects | Page-level metadata. Empty array `[]` is valid. |
| `pageSections` | array of section objects | The actual content. Empty `[]` for a blank page (then `sectionPosition` is also `[]`). |

That's the whole top level — do not invent extra fields.

## Meta object (entries in `meta`)

```json
{
  "id": 618435421616997327,
  "createdAt": "2026-05-07T09:23:56.225228Z",
  "updatedAt": "2026-05-07T09:23:56.225228Z",
  "deletedAt": null,
  "themePageID": 618435406517502927,
  "key": "global_layout",
  "value": "{\"showHeader\":true,\"showFooter\":true}",
  "edges": {}
}
```

`themePageID` must equal the parent page's `id`. `value` is a JSON-encoded string for structured values. Common keys:

- `lock_page_saved` — value is a numeric timestamp string.
- `global_layout` — value is `{"showHeader": bool, "showFooter": bool}` JSON-encoded.
- `seo_*` — SEO fields (title, description, keywords, og_image).

## pageSection object (entries in `pageSections`)

This is where most fields live. Each section object has:

| Field | Type | Notes |
|---|---|---|
| `id` | int64 | Referenced by top-level `sectionPosition` (as a string). |
| `createdAt` / `updatedAt` | ISO8601 string | Timestamps. |
| `deletedAt` | null \| ISO8601 string | `null` for active sections. |
| `shopId` | int64 | The shop that owns this section. |
| `themePageID` | int64 | Must equal the parent page's `id`. |
| `cid` | string | 10-char random ID (often starts with `g`). |
| `name` | string | Display name in the builder. |
| `component` | **string** | A JSON-encoded string holding the visual tree. See below. |
| `display` | bool | `true` for visible sections. |
| `isGlobal` | bool | `false` for normal sections; `true` for shared library sections. |
| `isMobile` | bool | Usually `false`. |
| `appBlocks` | string | Usually `""`. |
| `libraryPosition` | null \| array | `null` for normal sections. |
| `librarySectionID` | null \| int64 | `null` for normal sections. |
| `elementNames` | string | Comma-separated list of element tags used (e.g. `"Heading,Paragraph,Button"`). Used for indexing. |
| `globalStoreReleaseID` | int | Should match `manifest.json`'s `shop_curr_version`. |
| `customFontIDs` | null \| array | `null` if no custom fonts. |
| `checksum` | string | 64-char SHA-256 hex of the section content. GemPages recomputes on import. |
| `layoutColumns` | null \| int | Usually `null`. |
| `layoutRows` | null \| int | Usually `null`. |
| `edges` | object | Usually `{}`. |

**Critical:** `component` is a **JSON-encoded string**, not a nested object. If you `json.loads` the page JSON, `pageSections[i]["component"]` is still a string. To edit it: `json.loads(component)` → modify → `json.dumps(...)` → store back.

## Component tree (the parsed `component` string)

Once you parse `section["component"]`, you get the visual builder tree:

```json
{
  "uid": "gdocPFgqlL",
  "tag": "Section",
  "label": "Section",
  "settings": { "...": "..." },
  "styles": { "...": "..." },
  "advanced": { "...": "..." },
  "childrens": [
    {
      "uid": "g4EjVSIOil",
      "tag": "Col",
      "label": "Block",
      "settings": {},
      "styles": {},
      "advanced": { "...": "..." },
      "childrens": [
        {
          "uid": "gAAB9bdZTL",
          "tag": "Heading",
          "label": "Heading",
          "settings": {
            "text": "Your heading text goes here",
            "htmlTag": 2
          },
          "styles": { "...": "..." },
          "advanced": { "...": "..." }
        }
      ]
    }
  ]
}
```

- `uid` is a unique identifier (usually 10 chars, often starts with `g`). Each element has one.
- `tag` is the element type. Common values: `Section`, `Col`, `Row`, `Heading`, `Paragraph`, `Button`, `Image`, `Video`, `Container`, `Spacer`, `Divider`, `Form`, `Product`, `Collection`.
- `childrens` (note the trailing `s` — this is the literal field name GemPages uses, not standard English) is the array of child elements.
- `settings`, `styles`, `advanced` use breakpoint-keyed objects: `{"desktop": ..., "tablet": ..., "mobile": ...}` — you don't have to set all three; missing breakpoints inherit.
- `htmlTag` on `Heading` is an integer 1–6 corresponding to `<h1>`–`<h6>`.

## Minimal blank-page JSON

The smallest valid page JSON for a brand-new blank static page (no sections):

```json
{
  "id": 100000000000000001,
  "isMobile": false,
  "splitPercentage": 0,
  "name": "Blank Page",
  "type": "GP_STATIC",
  "description": "",
  "handle": "blank-page",
  "sectionPosition": [],
  "meta": [],
  "pageSections": []
}
```

GemPages accepts this on import and lets the user start adding sections in the builder.

## Minimal page-with-one-heading JSON

```json
{
  "id": 100000000000000001,
  "isMobile": false,
  "splitPercentage": 0,
  "name": "Hello Page",
  "type": "GP_STATIC",
  "description": "",
  "handle": "hello-page",
  "sectionPosition": ["200000000000000001"],
  "meta": [],
  "pageSections": [
    {
      "id": 200000000000000001,
      "createdAt": "2026-05-07T09:23:55.936354Z",
      "updatedAt": "2026-05-07T09:23:55.936355Z",
      "deletedAt": null,
      "shopId": 0,
      "themePageID": 100000000000000001,
      "cid": "gAAAAAAAAA",
      "name": "Section gAAAAAAAAA",
      "component": "{\"uid\":\"gAAAAAAAAA\",\"tag\":\"Section\",\"label\":\"Section\",\"settings\":{},\"styles\":{},\"advanced\":{},\"childrens\":[{\"uid\":\"gBBBBBBBBB\",\"tag\":\"Col\",\"label\":\"Block\",\"settings\":{},\"styles\":{},\"advanced\":{},\"childrens\":[{\"uid\":\"gCCCCCCCCC\",\"tag\":\"Heading\",\"label\":\"Heading\",\"settings\":{\"text\":\"Hello world\",\"htmlTag\":1},\"styles\":{},\"advanced\":{}}]}]}",
      "display": true,
      "isGlobal": false,
      "isMobile": false,
      "appBlocks": "",
      "libraryPosition": null,
      "librarySectionID": null,
      "elementNames": "Heading",
      "globalStoreReleaseID": 0,
      "customFontIDs": null,
      "checksum": "",
      "layoutColumns": null,
      "layoutRows": null,
      "edges": {}
    }
  ]
}
```

The `component` field is a JSON string. The IDs (`100000000000000001`, `200000000000000001`) are placeholders — GemPages will reassign on import, but they must be consistent within the file: `sectionPosition` references `200000000000000001` as a string, the section's own `id` is the same number, and `themePageID` matches the page's `id`.

## ID generation

GemPages IDs are 64-bit Snowflake-like integers (~17–19 digits). When generating IDs for a new export, any unused positive integer in that range works for round-tripping a build, but real GemPages servers will replace them on import. Keep them unique within a single export.
