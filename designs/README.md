# Stitch designs — all 4 screens

Visual previews from Google Stitch. **Mockups to imagine the product**, not production code.

To **run** the app: root [`README.md`](../README.md) · [`docs/13-HANDOFF.md`](../docs/13-HANDOFF.md).

Windows downloaded four copies of the same zip name; they are **four different screens**:

| Folder | Screen (MVP) | What you see |
|---|---|---|
| `stitch_redlineguard_contract_review_interface/` | **1 — Upload / Home** | Brand hero, dropzone, Select Document, Try a sample NDA |
| `stitch_redlineguard_contract_review_interface (1)/` | **2 — Processing** | Spinner, “Reading document…”, progress bar, est. time |
| `stitch_redlineguard_contract_review_interface (2)/` | **3 — Review** | Contract left + risk list right, highlights, Suggest rewrite |
| `stitch_redlineguard_contract_review_interface (3)/` | **4 — Rewrite decision** | Original vs suggested, Why this change, Accept / Edit / Reject |

Each folder has: `screen.png` · `code.html` · `DESIGN.md`

---

## Flow (matches `docs/00-WHAT-WE-ARE-BUILDING.md`)

```
(1) Upload  →  (2) Processing  →  (3) Review risks  →  (4) Accept/Edit/Reject rewrite
```

Open the four `screen.png` files in that order to walk the product mentally.

---

## What to keep when building

- Calm legal look (serif brand, muted chrome, teal primary)
- Upload → wait → split review → rewrite decision
- Risk highlights tied to a right-hand list
- Accept / Edit / Reject on the rewrite panel

## What to ignore (Stitch added extra chrome)

- Nav: Dashboard / Contracts / Team / Archive (and left sidebar variants)
- “AES-256 / GDPR” trust badges (don’t claim unbuilt security)
- Analysis score / Finalize Review / Market Align % (nice later, not MVP)
- Duplicate sidebars between screens 3 and 4 — pick one simple top bar for the real app

---

## Optional cleanup

Rename folders for clarity (when you want):

```
01_upload/
02_processing/
03_review/
04_rewrite_decision/
```
