# Setup Guide — GemPages Export Builder

## Requirements

- A **Claude Pro, Team, or Enterprise** account (Projects are not available on the free plan)
- The following files from this package:
  - `CLAUDE.md`
  - `SKILL.md`
  - `page_schema.md`
  - `build_gempages.py`

Choose the setup method that matches how you use Claude:

- **Option A** — [Claude Web (claude.ai)](#option-a--claude-web-claudeai)
- **Option B** — [Claude Desktop App (Cowork mode)](#option-b--claude-desktop-app-cowork-mode)

---

## Option A — Claude Web (claude.ai)

> **Note:** On claude.ai, Claude reads the knowledge files to understand the format and generate the correct JSON — but it cannot execute Python. You will receive the page JSON content, not a packaged `.gempages` file.

### Requirements

- The following files from this package:
  - `CLAUDE.md` — paste as Custom Instructions
  - `SKILL.md` — upload as Project Knowledge
  - `page_schema.md` — upload as Project Knowledge
  - `build_gempages.py` — upload as Project Knowledge

### Step 1 — Create a New Project

1. Go to https://claude.ai
2. In the left sidebar, click **Projects** → **New Project**
3. Name it: `GemPages Export Builder` (or any name you prefer)
4. Description: `Convert HTML code into a valid .gempages file that can be directly imported into the GemPages page builder on Shopify`

### Step 2 — Add Custom Instructions

![Project setup overview](https://cdn.shopify.com/s/files/1/0628/4515/7439/files/Screenshot_2026-05-08_at_12.04.35.png)

1. Inside the project, find the **Custom instructions** section (or **Set custom instructions**) on the right sidebar
2. Open `CLAUDE.md` in any text editor
3. Copy all the content and paste it into the Custom Instructions field
4. Save

### Step 3 — Upload Project Knowledge

1. Inside the project, find the **Files** section on the right sidebar (same screenshot above)
2. Click the **+** icon to upload files
3. Upload these **3 files**:
   - `SKILL.md`
   - `page_schema.md`
   - `build_gempages.py`
4. Wait a few seconds for Claude to finish indexing

### Step 4 — Test It

Open a new chat inside the project and try these prompts to verify everything is working:

**Prompt 1 — Quick check (verify Claude reads the skill files):**
> Create a simple sample .gempages file for me.

**Prompt 2 — Main use case (convert HTML to .gempages):**
> Please convert my HTML into a .gempages file so I can import it into GemPages on Shopify.
>
> `<paste your HTML code here — or attach your .html file above>`

Claude should answer based on the knowledge files. If responses are vague or generic, double-check that all 3 files were uploaded successfully.

---

## Option B — Claude Desktop App (Cowork mode)

> **Advantage over claude.ai:** Cowork mode has a live bash sandbox, so Claude can run `build_gempages.py` directly and deliver the actual `.gempages` file — no local Python setup needed.

### Requirements

- The **Claude desktop app** installed on your computer

### Step 1 — Open Cowork Mode

1. Open the **Claude desktop app**
2. Click **Cowork** in the sidebar (or start a new Cowork session)

### Step 2 — Select a Project Folder

1. When prompted, click **Select Folder**
2. Choose (or create) a folder on your computer, e.g. `GemPages Export Builder`
3. Claude will now have read/write access to that folder

### Step 3 — Add the Project Files

Copy all files from this package into the folder you selected:
- `CLAUDE.md`
- `SKILL.md`
- `page_schema.md`
- `build_gempages.py`

### Step 4 — Test It

Open a new chat inside the project and try these prompts to verify everything is working:

**Prompt 1 — Quick check (verify Claude reads the skill files):**
> Create a simple sample .gempages file for me.

**Prompt 2 — Main use case (convert HTML to .gempages):**
> Please convert my HTML into a .gempages file so I can import it into GemPages on Shopify.
>
> `<paste your HTML code here — or attach your .html file above>`

Claude should answer based on the knowledge files. If responses are vague or generic, double-check that all 3 files were placed in the project folder correctly.
