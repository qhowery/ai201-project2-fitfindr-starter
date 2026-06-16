# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset (`data/listings.json` via `load_listings()`) for secondhand items matching the user's description, optional size, and optional max price. Returns matching listings ranked by keyword relevance (best match first).

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g., `"vintage graphic tee"`). Tokenized into lowercase words; each token is matched against a listing's `title`, `description`, `style_tags`, and `category`.
- `size` (str | None): Optional size filter. If provided, keep only listings whose `size` field contains this string case-insensitively (e.g., `"M"` matches `"S/M"`). If `None`, skip size filtering.
- `max_price` (float | None): Optional price ceiling (inclusive). If provided, keep only listings where `listing["price"] <= max_price`. If `None`, skip price filtering.

**What it returns:**
A `list[dict]` of matching listing objects, sorted by relevance score (highest first). Each dict is a full listing with these fields:
- `id` (str): e.g., `"lst_006"`
- `title` (str): e.g., `"Graphic Tee — 2003 Tour Bootleg Style"`
- `description` (str): full item description
- `category` (str): one of `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`
- `style_tags` (list[str]): e.g., `["graphic tee", "vintage", "grunge", "streetwear", "band tee"]`
- `size` (str): e.g., `"L"`
- `condition` (str): `excellent`, `good`, or `fair`
- `price` (float): e.g., `24.00`
- `colors` (list[str]): e.g., `["black"]`
- `brand` (str | None): brand name or `null`
- `platform` (str): `depop`, `thredUp`, or `poshmark`

Returns `[]` (empty list) when no listings pass the filters or when every candidate scores 0 on keyword overlap. Does **not** raise an exception.

**What happens if it fails or returns nothing:**
The planning loop sets `session["error"]` to a user-facing message, leaves `selected_item`, `outfit_suggestion`, and `fit_card` as `None`, and returns the session immediately without calling `suggest_outfit` or `create_fit_card`. Example message: *"I couldn't find any listings matching 'vintage graphic tee' under $30. Try broadening your search — drop the size filter, increase your budget, or search for a different style."*

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted listing the user is considering and their existing wardrobe, calls the Groq LLM to produce 1–2 outfit suggestions. When the wardrobe has items, suggestions name specific pieces from the wardrobe by `name`. When the wardrobe is empty, the tool still succeeds and returns general styling advice based on the new item's `style_tags`, `colors`, and `category`.

**Input parameters:**
- `new_item` (dict): A full listing dict (same shape as one element from `search_listings` return value). Must include at least `title`, `category`, `style_tags`, and `colors`.
- `wardrobe` (dict): User wardrobe in the schema from `data/wardrobe_schema.json`. Shape: `{"items": [wardrobe_item, ...]}`. Each wardrobe item has:
  - `id` (str): e.g., `"w_001"`
  - `name` (str): e.g., `"Baggy straight-leg jeans, dark wash"`
  - `category` (str): `tops`, `bottoms`, `outerwear`, `shoes`, or `accessories`
  - `colors` (list[str])
  - `style_tags` (list[str])
  - `notes` (str | None): optional fit/styling notes

**What it returns:**
A non-empty `str` containing 1–2 outfit suggestions in plain English (roughly 3–8 sentences). When wardrobe has items, the string references specific wardrobe pieces by name (e.g., *"Pair this with your baggy straight-leg jeans and chunky white sneakers..."*). When wardrobe is empty, the string gives general pairing advice (e.g., *"This boxy graphic tee works with wide-leg denim and chunky sneakers for a 2000s streetwear look..."*) without naming wardrobe items.

**What happens if it fails or returns nothing:**
- **Empty wardrobe (`wardrobe["items"] == []`):** Not a failure. The tool calls the LLM with a prompt for general styling ideas and returns that string. The agent continues to `create_fit_card` and prepends a note in the final user output: *"I don't have your wardrobe yet, so this is general styling advice — add your pieces for personalized picks."*
- **LLM API error or empty/whitespace response:** The planning loop sets `session["error"]` to *"I couldn't generate outfit suggestions right now. Please try again in a moment."*, leaves `fit_card` as `None`, and returns the session early (keeping `selected_item` and `search_results` populated so the user still knows what was found).

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion text and the selected listing, then calls the Groq LLM (higher temperature for variety) to generate a short, casual social-media caption suitable for Instagram or TikTok.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit()`. Must be non-empty for a successful caption.
- `new_item` (dict): The same listing dict passed to `suggest_outfit`. Used for `title`, `price`, and `platform` in the caption.

**What it returns:**
A `str` containing a 2–4 sentence caption. The caption mentions the item name, price, and platform once each in a natural, casual tone (e.g., *"grabbed this '03-inspired bootleg tee from depop for $24 and the fit hits different with my baggy jeans 🖤 oversized all the way down"*).

**What happens if it fails or returns nothing:**
- **Empty or whitespace-only `outfit`:** The tool returns the string *"Cannot create a fit card — outfit suggestion is missing. Run suggest_outfit first."*` (does not raise). The planning loop detects this error prefix (or checks that `session["outfit_suggestion"]` was empty before calling) and sets `session["error"]` to *"I found a listing and outfit idea, but couldn't generate your fit card. Here's the outfit suggestion instead: [outfit_suggestion]"* — returning the outfit text in the error message so the user still gets partial value.
- **LLM API error:** The planning loop sets `session["error"]` to *"I couldn't generate a fit card right now, but here's your outfit idea: [outfit_suggestion]"* and returns the session with `fit_card` as `None`.

---

### Additional Tools (if any)

None. The three required tools are sufficient for the core flow.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent runs a **fixed sequential pipeline** (not dynamic tool selection). `run_agent(query, wardrobe)` executes these steps in order; any step that sets `session["error"]` causes an immediate return — no later tools run.

**Step 0 — Initialize**
- Call `_new_session(query, wardrobe)` to create the session dict.

**Step 1 — Parse query**
- Extract `description`, `size`, and `max_price` from `query` using regex:
  - `max_price`: match `under $XX`, `under XX dollars`, or `$XX` → float (e.g., `"under $30"` → `30.0`)
  - `size`: match `size M`, `size 8`, `in size L` → str (e.g., `"M"`)
  - `description`: remove price/size phrases from the query; strip filler words (`looking for`, `I want`, `what's out there`); remaining text becomes description (e.g., `"vintage graphic tee"`)
- Store in `session["parsed"]` as `{"description": str, "size": str | None, "max_price": float | None}`.
- If `description` is empty after parsing, set `session["error"]` = *"Tell me what you're looking for — e.g., 'vintage graphic tee under $30'."* and return.

**Step 2 — search_listings**
- Call `search_listings(description=session["parsed"]["description"], size=session["parsed"]["size"], max_price=session["parsed"]["max_price"])`.
- Store return value in `session["search_results"]`.
- **If `search_results` is empty:** set `session["error"]` with the no-results message (see Tool 1 failure mode) and return session.
- **If non-empty:** set `session["selected_item"] = search_results[0]` (top-ranked match) and continue.

**Step 3 — suggest_outfit**
- Call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`.
- Store return value in `session["outfit_suggestion"]`.
- **If return is empty/whitespace or LLM raised:** set `session["error"]` per Tool 2 failure mode and return session.
- **If wardrobe was empty:** set `session["wardrobe_note"]` = *"I don't have your wardrobe yet, so this is general styling advice."* (optional field for UI formatting).
- **Otherwise:** continue.

**Step 4 — create_fit_card**
- Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.
- Store return value in `session["fit_card"]`.
- **If return starts with `"Cannot create a fit card"` or is empty:** set `session["error"]` per Tool 3 failure mode (include outfit text in message) and return session.
- **Otherwise:** `session["error"]` stays `None` — interaction succeeded.

**Step 5 — Return session**
- Return the completed session dict. Caller (`app.py`) checks `session["error"]` first; if `None`, displays `selected_item`, `outfit_suggestion`, and `fit_card`.

**Done condition:** All three tools succeeded and `session["error"]` is `None`.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single **session dict** returned by `_new_session()` and mutated by `run_agent()`. No global variables or separate state object.

| Session key | Set when | Consumed by |
|-------------|----------|-------------|
| `query` | `_new_session()` | Reference only (original user input) |
| `parsed` | Step 1 (query parsing) | Step 2 (`search_listings` args) |
| `search_results` | Step 2 | Step 2 branch logic; optional UI display of alternates |
| `selected_item` | Step 2 (if results non-empty) | Steps 3 & 4 (`new_item` arg) |
| `wardrobe` | `_new_session()` (passed in) | Step 3 (`suggest_outfit` arg) |
| `outfit_suggestion` | Step 3 | Step 4 (`outfit` arg); error messages if Step 4 fails |
| `fit_card` | Step 4 | Final UI output |
| `error` | Any early-exit branch | UI: show in listing panel, clear other panels |
| `wardrobe_note` | Step 3 (if wardrobe empty) | Prepended to outfit panel in UI |

Data flow: `query` → `parsed` → `search_results` → `selected_item` → `outfit_suggestion` → `fit_card`. Each step reads only the keys it needs from the same session dict; no tool writes to session directly — only `run_agent()` updates session fields from tool return values.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` = *"I couldn't find any listings matching '{description}'{price_clause}. Try broadening your search — drop the size filter, increase your budget, or search for a different style."* where `{price_clause}` is `" under $30"` if max_price was set, else empty. Return session immediately. UI shows this message in the listing panel; outfit and fit card panels are blank. |
| suggest_outfit | Wardrobe is empty | **Not a hard failure.** Tool returns general styling advice. Agent sets `session["wardrobe_note"]` and continues to `create_fit_card`. Final outfit panel shows: *"[wardrobe_note] [outfit_suggestion]"*. |
| suggest_outfit | LLM returns empty string or API error | Set `session["error"]` = *"I found **{selected_item['title']}** (${selected_item['price']} on {selected_item['platform']}), but couldn't generate outfit suggestions right now. Please try again."* Return session with `fit_card` and `outfit_suggestion` as `None`. |
| create_fit_card | Outfit input is missing or incomplete | Before calling, guard: if `outfit_suggestion` is empty, skip LLM call and set `session["error"]` = *"Outfit suggestion was missing — can't create a fit card."* If tool returns the `"Cannot create a fit card..."` string, set `session["error"]` = *"Couldn't generate your fit card, but here's how to style it: {outfit_suggestion}"* so the user still sees the outfit idea in the listing panel. |

---

## Architecture

```
User query + wardrobe choice (Gradio UI)
    │
    ▼
run_agent(query, wardrobe)
    │
    ▼
Planning Loop ─────────────────────────────────────────────────────────────┐
    │                                                                        │
    ├─► Parse query → session["parsed"]                                     │
    │       │ parsed.description empty                                       │
    │       ├──► [ERROR] "Tell me what you're looking for..." → return       │
    │       │                                                                  │
    ├─► search_listings(description, size, max_price)                        │
    │       │ session["search_results"] = [...]                              │
    │       │ results = []                                                   │
    │       ├──► [ERROR] "I couldn't find any listings matching..." → return │
    │       │                                                                  │
    │       │ results = [item, ...]                                          │
    │       ▼                                                                  │
    │   session["selected_item"] = results[0]                                │
    │       │                                                                  │
    ├─► suggest_outfit(new_item=selected_item, wardrobe=wardrobe)          │
    │       │ session["outfit_suggestion"] = "..."                           │
    │       │ wardrobe.items empty → session["wardrobe_note"] set (continue) │
    │       │ empty/LLM error                                                  │
    │       ├──► [ERROR] "couldn't generate outfit suggestions..." → return  │
    │       │                                                                  │
    ├─► create_fit_card(outfit=outfit_suggestion, new_item=selected_item)    │
    │       │ session["fit_card"] = "..."                                    │
    │       │ outfit missing / tool error                                    │
    │       ├──► [ERROR] partial message with outfit_suggestion → return     │
    │       │                                                                  │
    └─► session["error"] = None → return session ──────────────────────────┘
            │
            ▼
    handle_query() formats session → 3 UI panels
    (listing_text, outfit_suggestion, fit_card)
```

**Component summary:**
- **User** submits natural-language query and wardrobe choice via Gradio.
- **Planning loop** (`run_agent`) owns sequential control flow and session mutation.
- **Tools** are pure functions — they receive inputs and return values; they do not read or write session.
- **Session state** is the data bus between steps; error branches write `session["error"]` and return early to the UI.

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

| Tool | AI tool | Input to AI | Expected output | Verification |
|------|---------|-------------|-----------------|--------------|
| `search_listings` | Claude (Cursor) | Tool 1 block from this doc (inputs, return shape, failure mode) + note to use `load_listings()` from `utils/data_loader.py` | A function that filters by price/size, scores keyword overlap, sorts by score, returns `list[dict]` | Run 3 manual tests: (1) `"vintage graphic tee"`, max_price=30 → expect lst_006 or lst_033 in results; (2) `"designer ballgown"`, max_price=5 → expect `[]`; (3) size `"M"` filter excludes wrong sizes. Confirm no exceptions on empty results. |
| `suggest_outfit` | Claude (Cursor) | Tool 2 block + wardrobe schema fields + note to use `_get_groq_client()` pattern from `tools.py` | Function calling Groq with wardrobe-aware or general prompt; returns non-empty `str` | Test with `get_example_wardrobe()` + lst_006: response names at least one wardrobe item (e.g., baggy jeans). Test with `get_empty_wardrobe()`: response gives general advice, no exception. |
| `create_fit_card` | Claude (Cursor) | Tool 3 block + caption style guidelines from `tools.py` docstring | Function with empty-outfit guard + Groq call at higher temperature; returns 2–4 sentence `str` | Pass a sample outfit string + lst_006: caption mentions title/price/platform once each. Pass `outfit=""`: returns error string, no exception. |

**Milestone 4 — Planning loop and state management:**

| Component | AI tool | Input to AI | Expected output | Verification |
|-----------|---------|-------------|-----------------|--------------|
| `run_agent` + `_new_session` | Claude (Cursor) | Planning Loop section, State Management table, Architecture diagram, and `agent.py` TODO comments | `run_agent()` that parses query, runs tools in sequence, populates session dict, returns early on errors | Run `python agent.py`: happy path prints selected item title + outfit + fit card; no-results path prints error message. Compare session keys against State Management table. |
| `handle_query` in `app.py` | Claude (Cursor) | Architecture diagram + session key descriptions + `app.py` TODO | Gradio handler mapping session to 3 output strings | Launch `python app.py`, submit example query, confirm 3 panels populate. Submit empty query → error in panel 1 only. |

Before accepting any AI-generated code, I will diff it against the Tool specs above: correct parameter names/types, session keys match `_new_session`, and each error branch sets `session["error"]` with the exact messages defined in Error Handling.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Setup:** User selects "Example wardrobe" in Gradio. `handle_query` calls `run_agent(query, get_example_wardrobe())`.

**Step 0 — Initialize session**
- `session = _new_session(query, example_wardrobe)`
- `session["wardrobe"]["items"]` has 10 pieces including baggy jeans (`w_001`) and chunky white sneakers (`w_007`).

**Step 1 — Parse query**
- Regex extracts: `max_price = 30.0`, `size = None`, `description = "vintage graphic tee"`
- `session["parsed"] = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}`

**Step 2 — Search for matching listings**
- Agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`.
- Tool loads 40 listings, filters to price ≤ $30, scores keyword overlap for `vintage`, `graphic`, `tee`.
- Returns 3 matches (sorted by score):
  1. `lst_006` — "Graphic Tee — 2003 Tour Bootleg Style", $24, depop, size L, tags: `["graphic tee", "vintage", "grunge", "streetwear", "band tee"]`
  2. `lst_033` — "Vintage Band Tee — Faded Grey", $19, depop, size L
  3. `lst_002` — "Y2K Baby Tee — Butterfly Print", $18, depop, size S/M
- `session["search_results"]` = all 3; `session["selected_item"]` = `lst_006` (highest score — title directly matches "Graphic Tee" + "vintage" tag).
- *(If no listings matched: agent would set `session["error"]` = "I couldn't find any listings matching 'vintage graphic tee' under $30..." and return — no further steps.)*

**Step 3 — Suggest an outfit with the new item**
- Agent calls `suggest_outfit(new_item=lst_006_dict, wardrobe=example_wardrobe)`.
- LLM prompt includes lst_006 details (black boxy graphic tee, streetwear/grunge tags) and wardrobe items (baggy jeans, chunky sneakers, black denim jacket, etc.).
- Returns string like: *"Pair the Graphic Tee — 2003 Tour Bootleg Style with your baggy straight-leg jeans and chunky white sneakers for an easy 2000s streetwear look. The boxy fit balances the volume of the wide legs. Layer your vintage black denim jacket over it if it's chilly — the all-black top half keeps the bootleg graphic as the focal point."*
- `session["outfit_suggestion"]` = that string. Wardrobe is not empty, so no `wardrobe_note`.

**Step 4 — Generate a shareable fit card**
- Agent calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=lst_006_dict)`.
- LLM returns caption like: *"scored this '03 bootleg-style tee on depop for $24 and threw it on with my baggy dark-wash jeans + chunky whites 🤍 oversized top, wide leg bottom — the 2000s formula never misses"*
- `session["fit_card"]` = that string; `session["error"]` = `None`.

**Step 5 — Format for UI**
- `handle_query` formats `selected_item` into listing panel:
  ```
  Graphic Tee — 2003 Tour Bootleg Style
  $24.00 on depop · Size L · good condition
  Vintage-style bootleg tee with faded graphic. Slightly boxy fit...
  ```
- Outfit panel = `session["outfit_suggestion"]`
- Fit card panel = `session["fit_card"]`

**Final output to user (all three panels):**
- **Listing:** Graphic Tee — 2003 Tour Bootleg Style ($24 on Depop, size L, good condition) with full description.
- **Outfit:** Pair with baggy straight-leg jeans and chunky white sneakers; optional black denim jacket layer.
- **Fit card:** Casual caption mentioning depop, $24, and the styling vibe.

If the user had selected "Empty wardrobe" instead, Steps 2–4 would still run, but Step 3 would return general advice (e.g., *"Style this boxy vintage tee with wide-leg denim and chunky sneakers..."*) and the outfit panel would prepend: *"I don't have your wardrobe yet, so this is general styling advice — add your pieces for personalized picks."*
