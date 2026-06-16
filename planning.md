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
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1: Search for matching listings**
Agent calls `search_listings(description="vintage graphic tee", max_price=30.0, size=None)`. The tool filters the listings dataset by price (≤$30), searches title/description for "graphic tee" and "vintage", and returns 2–3 matching items sorted by relevance. Agent picks the top result: lst_006 "Graphic Tee — 2003 Tour Bootleg Style" at $24. If no listings match, the agent tells the user "I couldn't find any vintage graphic tees under $30. Try searching for a different style or increasing your budget" and stops.

**Step 2: Suggest an outfit with the new item**
Agent calls `suggest_outfit(new_item=lst_006_dict, wardrobe=user_wardrobe)` where user_wardrobe contains their baggy jeans, chunky sneakers, and other pieces. The tool analyzes style compatibility using color and style_tags, then returns outfit suggestions like "Pair this with your baggy jeans and chunky white sneakers for a 2000s streetwear vibe. The boxy fit of this tee balances the volume of the wide-legs." If the wardrobe is empty, the agent tells the user "I need to know more about your style first — tell me about pieces you already own" and stops without calling create_fit_card.

**Step 3: Generate a shareable fit card**
Agent calls `create_fit_card(outfit=outfit_dict, new_item=lst_006_dict)` to generate a social media caption. The tool crafts a short, punchy post: "grabbed this '03-inspired bootleg tee from depop for $24 and the fit hits different with my baggy jeans 🖤 oversized all the way down". The agent returns this to the user along with the suggested outfit pairing.

**Final output to user:**
"Found it! 🎯 **Graphic Tee — 2003 Tour Bootleg Style** ($24 on Depop, good condition). Here's how to style it: [outfit suggestion]. Try this caption: [fit card text]."
