# FitFindr

FitFindr is a secondhand shopping agent that searches mock thrift listings, suggests outfits based on your existing wardrobe, and generates a shareable social-media fit card. The agent runs a **fixed sequential planning loop** — it does not call all three tools unconditionally. If search returns nothing, the loop stops before any LLM tools run.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key ([console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

### Run the app

```bash
python app.py
```

Open the URL printed in your terminal (usually `http://localhost:7860`). Submit a query like **"vintage graphic tee under $30"** with **Example wardrobe** selected — all three output panels should populate.

### Run tests

```bash
pytest tests/ -v
```

25 tests cover individual tools, the planning loop, and deliberate failure modes.

---

## Project structure

```
ai201-project2-fitfindr-starter/
├── agent.py              # Planning loop and session state
├── app.py                # Gradio UI
├── tools.py              # Three agent tools
├── planning.md           # Pre-implementation spec
├── data/
│   ├── listings.json     # 40 mock secondhand listings
│   └── wardrobe_schema.json
├── utils/data_loader.py
└── tests/
    ├── test_tools.py
    ├── test_agent.py
    └── test_failure_modes.py
```

---

## Tool inventory

### 1. `search_listings`

**Purpose:** Find secondhand listings in the mock dataset that match the user's description, optional size, and optional price ceiling.

| Parameter | Type | Meaning |
|-----------|------|---------|
| `description` | `str` | Keywords to match (e.g. `"vintage graphic tee"`) |
| `size` | `str \| None` | Size filter; case-insensitive substring match (e.g. `"M"` matches `"S/M"`) |
| `max_price` | `float \| None` | Maximum price inclusive; `None` skips price filtering |

**Returns:** `list[dict]` — matching listing dicts sorted by relevance (best first). Each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` when nothing matches — never raises.

**Implementation notes:** Loads data via `load_listings()`. Filters by price/size, scores keyword overlap (title weighted highest), drops zero-score results.

---

### 2. `suggest_outfit`

**Purpose:** Given a listing the user might buy and their wardrobe, produce 1–2 outfit suggestions using Groq `llama-3.3-70b-versatile`.

| Parameter | Type | Meaning |
|-----------|------|---------|
| `new_item` | `dict` | Full listing dict from `search_listings` |
| `wardrobe` | `dict` | `{"items": [...]}` per `wardrobe_schema.json` |

**Returns:** `str` — 3–8 sentences of outfit advice. Names specific wardrobe pieces when items exist; gives general pairing advice when wardrobe is empty.

**Implementation notes:** Two prompt branches (empty vs populated wardrobe). Falls back to a hardcoded string if the LLM returns empty text.

---

### 3. `create_fit_card`

**Purpose:** Generate a casual 2–4 sentence Instagram/TikTok caption for the find and outfit.

| Parameter | Type | Meaning |
|-----------|------|---------|
| `outfit` | `str` | Outfit suggestion from `suggest_outfit` |
| `new_item` | `dict` | Same listing dict used in `suggest_outfit` |

**Returns:** `str` — social caption mentioning item name, price, and platform once each. If `outfit` is empty/whitespace, returns `"Cannot create a fit card — outfit suggestion is missing. Run suggest_outfit first."` without raising.

**Implementation notes:** Uses Groq at temperature `0.9` so repeated calls on the same input produce varied captions.

---

## Planning loop

The agent does **not** dynamically pick tools. `run_agent(query, wardrobe)` runs a fixed pipeline and **returns early** whenever a step fails.

```
User query
    │
    ▼
Parse query (regex) ──► empty description? ──► ERROR, return
    │
    ▼
search_listings ──► results == []? ──► ERROR, return (skip LLM tools)
    │
    ▼
selected_item = results[0]
    │
    ▼
suggest_outfit(selected_item, wardrobe) ──► empty/LLM error? ──► ERROR, return
    │
    ▼
create_fit_card(outfit_suggestion, selected_item) ──► error string? ──► ERROR, return
    │
    ▼
Return session (error = None)
```

### Decisions the agent makes

1. **What to search for** — `_parse_query()` extracts `description`, `size`, and `max_price` from natural language using regex (not the LLM). Filler phrases like "looking for" are stripped; price phrases like "under $30" become `max_price=30.0`.

2. **Whether to continue after search** — If `search_results` is empty, the agent sets a specific error message and **does not call** `suggest_outfit` or `create_fit_card`. This is the most important branch — without it, the agent would run LLM tools on nothing.

3. **Which listing to style** — Always the top-ranked result (`search_results[0]`), not user choice (stretch goal could add alternates).

4. **How to handle empty wardrobe** — Not a hard stop. `suggest_outfit` returns general advice; the agent sets `wardrobe_note` and still calls `create_fit_card`.

5. **When the interaction is done** — Success means all three tools ran and `session["error"]` is `None`. Any early return leaves later session fields as `None`.

---

## State management

All state lives in a single **session dict** created by `_new_session()` and returned by `run_agent()`. Tools are pure functions — they receive inputs and return values; only `run_agent()` writes to the session.

| Key | Set when | Used by |
|-----|----------|---------|
| `query` | Session init | Reference |
| `parsed` | After query parsing | `search_listings` args |
| `search_results` | After search | Branch logic |
| `selected_item` | Top result selected | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | Session init | `suggest_outfit` |
| `outfit_suggestion` | After `suggest_outfit` | `create_fit_card` |
| `fit_card` | After `create_fit_card` | UI output |
| `wardrobe_note` | Empty wardrobe path | Prepended in outfit panel |
| `error` | Any early exit | UI listing panel |

**State flow example** (happy path for `"vintage graphic tee under $30"`):

```
query → parsed: {description: "vintage graphic tee", max_price: 30.0}
      → search_results: [lst_006, lst_033, lst_002]
      → selected_item: lst_006 dict (same object passed to suggest_outfit)
      → outfit_suggestion: "Pair with your baggy straight-leg jeans..."
      → fit_card: "scored this bootleg tee on depop for $24..."
```

The same `selected_item` dict flows into both LLM tools without re-fetching or hardcoding.

---

## Error handling

| Tool | Failure | Agent / tool response |
|------|---------|-------------------------|
| `search_listings` | No matches | Early return. Example from testing: query `"designer ballgown size XXS under $5"` → `[]` at tool level; agent message: *"I couldn't find any listings matching 'designer ballgown' under $5. Try broadening your search — drop the size filter, increase your budget, or search for a different style."* Outfit and fit card panels stay blank. |
| `suggest_outfit` | Empty wardrobe | **Not a failure.** Tool returns general styling advice. Agent sets `wardrobe_note` and continues. Tested with `get_empty_wardrobe()` — returned 680+ chars of pairing advice, no exception. |
| `suggest_outfit` | LLM error / empty | Early return with message naming the found item: *"I found **Graphic Tee — 2003 Tour Bootleg Style** ($24.0 on depop), but couldn't generate outfit suggestions right now."* |
| `create_fit_card` | Empty outfit | Tool returns `"Cannot create a fit card — outfit suggestion is missing..."`. Verified: `create_fit_card('', item)` returns that string, no Python exception. Agent maps tool error to user message including the outfit text when partial success occurred. |

### How to trigger failures manually

```bash
# No results
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"

# Empty wardrobe (needs GROQ_API_KEY)
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
r = search_listings('vintage graphic tee', max_price=50)
print(suggest_outfit(r[0], get_empty_wardrobe()))
"

# Empty outfit
python -c "
from tools import search_listings, create_fit_card
r = search_listings('vintage graphic tee', max_price=50)
print(create_fit_card('', r[0]))
"
```

---

## Spec reflection

| Spec (planning.md) | Implementation | Notes |
|--------------------|----------------|-------|
| Regex query parsing | `_parse_query()` in `agent.py` | Added article stripping (`"a vintage..."` → `"vintage..."`) and first-sentence truncation so wardrobe context in long queries doesn't pollute search |
| Title-weighted search scoring | `_score_listing()` in `tools.py` | Initial equal-weight scoring ranked wrong item first; added title weight + tiebreaker so `lst_006` ranks top for graphic tee queries |
| Empty wardrobe continues | `run_agent()` + `suggest_outfit()` | Spec said stop in walkthrough draft but `tools.py` stub required general advice; implemented continue-with-note approach |
| Early return on empty search | `run_agent()` line 139 | Verified with pytest — `suggest_outfit` and `create_fit_card` are never called when search returns `[]` |
| Fit card temperature 0.9 | `FIT_CARD_TEMPERATURE = 0.9` | Tested manually — repeated calls produce different captions |

---

## AI tool usage

I used **Cursor (Claude)** throughout, feeding it sections from `planning.md` rather than open-ended "help me code" prompts.

### Instance 1 — Implementing `search_listings`

**Input given:** Tool 1 block from `planning.md` (parameters, return shape, failure mode) + instruction to use `load_listings()`.

**Output produced:** Initial implementation with equal keyword scoring across title, description, and tags.

**What I changed:** The generated scorer ranked `lst_002` above `lst_006` for `"vintage graphic tee under $30"`. I overrode scoring to weight title matches 3×, tag matches 2×, and added a title-keyword tiebreaker — matching the spec's intent that the bootleg graphic tee ranks first. Added pytest tests before trusting the function.

### Instance 2 — Implementing `run_agent`

**Input given:** Architecture ASCII diagram + Planning Loop and State Management sections from `planning.md` + `agent.py` TODO comments.

**Output produced:** Sequential loop with session mutations and early returns.

**What I changed:** Added article stripping in `_parse_query()` because the AI left `"a vintage graphic tee"` as the description, which still worked but didn't match the spec. Added `wardrobe_note` to the session dict for UI formatting. Wrote `tests/test_agent.py` to verify the no-results branch never calls downstream tools — the generated code had the branch, but tests confirmed it.

---

## Demo video guide (3–5 minutes)

Record yourself running `python app.py`. Suggested structure:

### 1. Happy path (~2 min)

- **Query:** `"vintage graphic tee under $30"` + Example wardrobe
- **Narrate Step 1:** "The agent parses my query into description and max price, then calls `search_listings`."
- **Point at listing panel:** Show `lst_006` — Graphic Tee, $24, Depop
- **Narrate Step 2:** "That exact listing dict is stored as `selected_item` and passed to `suggest_outfit` with my wardrobe."
- **Point at outfit panel:** Mention baggy jeans / chunky sneakers by name
- **Narrate Step 3:** "`outfit_suggestion` flows into `create_fit_card` to generate the caption."
- **Point at fit card panel**

**State passing moment:** Open a terminal beside the app and run:
```bash
python agent.py
```
Show `selected_item id: lst_006` and narrate that the same object flows through all three tools.

### 2. Failure mode (~1 min)

- Click example query **"designer ballgown size XXS under $5"**
- **Narrate:** "Search returned zero results, so the agent stopped — no outfit or fit card generated."
- Show the actionable error in the listing panel (suggests dropping size filter, increasing budget)
- Optional: mention `fit_card is None` from `python agent.py` no-results section

### 3. Wrap-up (~30 sec)

- Mention 25 pytest tests including deliberate failure mode tests
- Reference `planning.md` as the spec that drove implementation

---

## Example queries

| Query | Expected behavior |
|-------|-------------------|
| `vintage graphic tee under $30` | Happy path — all 3 panels |
| `90s track jacket in size M` | Search with size filter |
| `designer ballgown size XXS under $5` | No results error |
| Empty wardrobe + any happy query | General styling advice + wardrobe note |

---

## License

CodePath AI201 — Project 2 starter kit.
