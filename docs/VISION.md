# Personal Health Observability System — Product & Technical Vision

## 1. Product vision

Build a **single-user, self-hosted personal nutrition and cooking system**.

The system should become my personal source of truth for:

- what I eat
- what I cook
- the ingredients and products I use
- nutritional information
- recipe development and iteration
- meal prep batches and remaining portions
- historical cooking notes
- eventually other health signals

The primary design goal is **not perfect tracking**.

The primary design goal is:

> Make capturing useful health data so frictionless that incomplete tracking is still worth doing.

I have previously benefited from tracking food, but traditional calorie-tracking applications eventually fail because entering data requires too much work. Missing one meal can also create an all-or-nothing failure mode.

This system should explicitly avoid that.

A day with 70% of meals captured is valuable.

A meal logged as:

> "Had a large chicken curry with rice at the office, probably around 800 kcal"

is better than an unlogged meal.

Do not force artificial precision.

---

# 2. Guiding principles

### Capture first, structure second

The user should be able to provide:

- natural-language text
- voice/transcribed speech
- images
- barcode/product information
- references to previously cooked food

Examples:

> I ate one portion of the chicken curry from Monday.

> I had two slices of pizza and a beer with friends around 8pm.

> [photo of supermarket package]

> I cooked the curry again today but used 600g chicken instead of 500g.

The system should translate these into structured records.

---

### Never require completeness

Fields should be allowed to be:

- known
- estimated
- inferred
- unknown

For example:

```text
calories: 750
confidence: estimated
range: 600–900
```

is legitimate.

Do not invent exact nutrition numbers simply because the database schema expects them.

---

### Preserve the original observation

Every agent-generated mutation should retain the original user input.

For example:

```text
raw_input:
"I ate one portion of yesterday's curry at around 1"
```

alongside the normalized representation.

This gives us:

- auditability
- the ability to reprocess data later
- protection against incorrect LLM interpretation

---

### LLMs interpret. Code executes.

The LLM should **never receive unrestricted SQL access**.

Instead:

```text
LLM
 ↓
well-defined tools / API
 ↓
domain service
 ↓
PostgreSQL
```

The domain layer enforces invariants.

---

### Append rather than destroy

Health history should behave somewhat like an event log.

Corrections should preferably retain history rather than silently overwriting the past.

Example:

```text
13:04 meal logged
13:10 quantity corrected
13:12 product nutrition corrected
```

The current state can be materialized from those changes.

Full event sourcing is unnecessary for V1, but auditability should be preserved.

---

# 3. V1 scope

V1 has exactly four major domains.

### Food catalog

Store reusable food/products/ingredients.

Examples:

```text
Chicken breast
REWE Greek yogurt
Red lentils
Homemade curry sauce
```

Store nutrition primarily per 100 g / 100 ml where applicable.

Possible fields:

```text
name
brand
barcode
serving information

energy_kcal
protein_g
carbohydrate_g
fat_g
fiber_g

source
source_url
confidence
```

Start with the selected nutrient columns and add others when they become useful.

---

### Recipes

A recipe is a logical object with **immutable versions**.

For example:

```text
Chicken Curry
 ├─ v1 - 2026-09-02
 ├─ v2 - 2026-09-09
 └─ v3 - 2026-09-20
```

A version contains:

```text
ingredients
ingredient quantities
instructions
expected portions
nutrition calculation
notes
```

Critically, historical cooking sessions must remain connected to the version actually used.

Changing today's recipe must not change nutrition for a meal eaten three weeks ago.

---

# 4. Recipe experimentation

Recipe development is one of the central features.

Each cooking session should become a **cook/batch record**.

Example:

```text
Recipe:
Chicken Curry

Version:
v4

Cooked:
2026-09-21 18:30

Yield:
8 portions

Changes:
- 100 ml less coconut milk
- 15 g instead of 25 g chili paste

Notes:
- texture excellent
- still slightly too spicy

Next-time note:
Use 10 g chili paste.
```

When I later say:

> I want to cook my chicken curry.

the system should be able to retrieve:

- current recipe
- last cooked version
- previous cooking notes
- suggested changes I explicitly recorded

It should say something like:

> The last batch was v4. You liked the texture but noted that it was still slightly too spicy. Your note for next time was to reduce chili paste from 15 g to 10 g.

That is **retrieval of my own recorded intent**, not autonomous recipe recommendation.

---

# 5. Meal-prep model

Meal prep should be a first-class concept.

When I cook:

```text
2400 g finished curry
8 portions
```

create a `food_batch`.

Example:

```text
Batch #123
Recipe version: curry v4
Cooked: Sep 21
Yield: 8 portions
Remaining: 8
```

Then:

> I ate one curry portion for lunch.

becomes:

```text
consumption
  batch_id = 123
  quantity = 1 portion
```

and:

```text
remaining portions: 7
```

Nutrition is inherited from the batch.

This makes logging meal-prepped food extremely cheap.

---

# 6. Consumption log

The core event is:

```text
ConsumptionEvent
```

Conceptually:

```text
timestamp
food/batch/recipe reference
amount
unit
nutrition estimate
source
confidence
raw observation
```

The source might be:

```text
manual
signal
chatgpt
photo
barcode
agent inference
```

Examples should all be legal:

```text
exact:
250 g yogurt
```

```text
portion-based:
1 portion curry
```

```text
estimate:
roughly half a restaurant pizza
```

```text
unknown:
dinner at Italian restaurant
```

Unknown nutrition should **not prevent logging**.

---

# 7. Handling uncertainty

This is important enough to build into the domain model.

A value should optionally have provenance.

For example:

```json
{
  "energy_kcal": 710,
  "confidence": "estimated",
  "min": 600,
  "max": 850,
  "source": "agent_estimate"
}
```

Confidence might be:

```text
verified
calculated
database
label
estimated
unknown
```

Therefore the dashboard can distinguish:

```text
Consumed today:
1,840 kcal known/calculated
+ approximately 400–700 kcal estimated
```

rather than pretending:

```text
2,416 kcal
```

when the underlying evidence doesn't justify that precision.

---

# 8. Input architecture

There should be **many capture interfaces but one backend**.

Conceptually:

```text
                 ┌───────────────┐
Signal ----------│               │
                 │               │
ChatGPT / MCP ---│  Health API   │---- PostgreSQL
                 │               │
Dashboard -------│               │
                 │               │
Future apps -----│               │
                 └───────────────┘
```

Do not implement domain behavior separately inside Signal, ChatGPT and the UI.

Everything talks to the same application API.

---

# 9. Signal / Hermes workflow

Hermes acts primarily as a capture agent.

Example:

### Input

Photo of a supermarket sandwich plus:

> Eating this now.

### Agent

1. inspect image
2. identify product
3. search local food database
4. if missing, obtain nutritional information
5. create/reuse food item
6. determine portion
7. create consumption event
8. acknowledge briefly

Response:

> Logged the full sandwich for 12:43.

Don't require a six-message dialogue.

---

Another example:

> Just had one of Monday's curry portions.

Agent:

```text
search recent batches
→ Chicken Curry batch Sep 19
→ 4 portions remaining
```

Then:

```text
create consumption
decrement conceptual remaining count
```

Response:

> Logged one portion of Monday's chicken curry.

---

# 10. Ambiguity policy

The agent should only ask a question when the ambiguity meaningfully affects the result.

Bad:

> How many grams was the apple?

Better:

> Logged one medium apple as an estimate.

But:

> I ate curry.

when there are three active curry batches may justify:

> Do you mean the chicken curry from Monday or the lentil curry from yesterday?

Prefer sensible inference over unnecessary interaction.

---

# 11. Agent tool surface

Do **not** create hundreds of microscopic MCP tools.

Start with roughly these concepts:

```text
search_food
get_food

create_food
update_food

search_recipes
get_recipe
create_recipe
create_recipe_version

record_cooking
get_recent_cooking_history

list_active_batches
get_batch

log_consumption
update_consumption
delete_consumption

get_consumption_history
get_daily_nutrition

add_recipe_note

search_everything
```

Tool inputs and outputs should be strongly typed.

Example:

```json
log_consumption({
  "occurred_at": "...",
  "food_reference": {...},
  "quantity": 1,
  "unit": "portion",
  "raw_input": "...",
  "confidence": "high"
})
```

MCP should essentially expose the application service layer.

---

# 12. Natural-language temporal resolution

The system needs to understand phrases such as:

> yesterday

> Monday

> this morning

> at lunch

> the curry I cooked two days ago

The LLM can resolve the language, but the backend should receive explicit timestamps.

Always retain:

```text
raw phrase
resolved timestamp
```

Timezone:

```text
Europe/Berlin
```

internally store timestamps as timezone-aware values.

---

# 13. Dashboard

The dashboard should initially be deliberately small.

I want to open it on my iPhone and immediately see:

```text
TODAY

Calories
1,730 kcal

Protein
126 g

Fiber
24 g

Meals
08:40 Breakfast
12:37 Chicken curry
16:10 Protein pudding

Estimated / uncertain items
Dinner: ~500–750 kcal
```

And possibly:

```text
Current meal prep

Chicken Curry
5 portions left

Chia pudding
2 portions left
```

No giant analytics platform initially.

---

# 14. Dashboard interaction

Build it mobile-first as a **PWA**.

On iPhone:

```text
Tailscale
   ↓
private home network
   ↓
https://health.<private-domain>
```

I can add the site to the iPhone Home Screen.

It should feel approximately like a native app.

Important:

- responsive
- fast
- touch-friendly
- dark mode
- works well one-handed
- minimal navigation

The dashboard doesn't need to be publicly exposed.

---

# 15. Networking

Initial deployment should be entirely self-hosted.

Something approximately like:

```text
Internet
   │
   │ outbound traffic only
   │
┌──▼──────────────── Home server ──────────────┐
│                                              │
│ Postgres                                     │
│ Health API                                   │
│ Hermes                                       │
│ MCP adapter                                  │
│ Dashboard                                    │
│ reverse proxy                                │
│                                              │
└───────────────────┬──────────────────────────┘
                    │
                 Tailscale
                    │
                  iPhone
```

No inbound port-forwarding should be required for the dashboard.

Tailscale provides private connectivity.

---

# 16. Deployment

Keep V1 boring.

Use:

```text
Docker Compose
```

not Kubernetes.

Possible containers:

```yaml
postgres
api
dashboard
hermes
mcp
reverse-proxy
```

Potentially:

```text
Caddy
```

for internal TLS/reverse proxy.

Do not introduce Kubernetes until there is an actual problem Kubernetes solves.

---

# 17. Technology choices

Prefer boring, maintainable technology.

### Database

PostgreSQL.

Reasons:

- relational model fits the domain extremely well
- JSONB available where flexibility is useful
- excellent tooling
- trivial scale requirements
- easy backup
- extensible later

Do not start with a graph database.

---

### Backend

My preference would be:

```text
Go
```

for the domain API.

Something like:

```text
Go
PostgreSQL
sqlc
goose
chi
```

would be more than sufficient.

Keep domain logic independent of HTTP/MCP.

Structure roughly:

```text
/domain
/service
/repository
/http
/mcp
```

The MCP server should call the same services the HTTP API calls.

---

### Frontend

Use whatever allows rapid development.

For example:

```text
Next.js
```

or

```text
SvelteKit
```

The backend remains the source of truth.

---

# 18. Image storage

Do not put large images directly in PostgreSQL.

Store:

```text
/uploads/...
```

on disk initially.

Database stores:

```text
path
mime_type
hash
created_at
```

Later this abstraction could point to S3-compatible storage.

Do not deploy MinIO on day one unless necessary.

---

# 19. Data provenance

Every externally obtained nutrition value should carry its source.

For example:

```text
source_type: manufacturer
source_url: ...
retrieved_at: ...
```

or:

```text
source_type: package_photo
```

or:

```text
source_type: user_entered
```

This becomes valuable when two sources disagree.

---

# 20. Duplicate detection

Foods should not proliferate endlessly.

For packaged products, use:

```text
barcode
brand
name
```

For ingredients use normalization.

For example:

```text
chickpeas
Chick Peas
Kichererbsen
```

may refer to a canonical ingredient while retaining aliases.

Do not make deduplication overly clever in V1.

---

# 21. Corrections must be extremely easy

Natural corrections should work.

For example:

> Actually that wasn't 300 grams, it was 200.

or:

> Delete the yogurt I logged this morning.

or:

> The curry was yesterday, not today.

The agent should infer the referenced recent event and update it.

These operations should be auditable.

---

# 22. ChatGPT cooking experience

This is a different interface over the same data.

While cooking I should be able to say:

> Pull up my chicken curry.

Then:

> What did I change last time?

Then:

> Okay, let's use 10 grams of chili paste today.

Then:

> Actually I'm using 700 grams of chicken.

Then:

> Save this as today's version.

At the end:

> Finished. It made nine portions.

The agent should then create:

```text
new recipe version if appropriate
cook event
batch
nutrition per portion
```

without requiring me to manually enter these things later.

---

# 23. Keep agent reasoning ephemeral

Do not store arbitrary LLM thoughts.

Persist only relevant artifacts:

```text
user observation
normalized interpretation
tool calls/results
confidence/provenance
final domain changes
```

The database is the memory.

The LLM is not the memory.

This distinction is extremely important.

---

# 24. Explicitly out of scope for V1

Do not implement:

- exercise tracking
- Apple Health
- sleep
- weight prediction
- personalized health coaching
- AI dietary recommendations
- meal recommendations
- grocery optimization
- continuous glucose data
- biomarker tracking
- medical diagnosis
- family/multi-user support
- OAuth
- complicated RBAC
- cloud deployment
- Kubernetes
- event streaming
- Kafka
- vector databases unless a concrete use case emerges

These are future possibilities, not current requirements.

---

# 25. V1 success criterion

I should be able to use the system for **two weeks without opening a traditional calorie-tracking application**.

The following flows must feel effortless:

```text
"I ate this."
```

```text
"I ate one portion of yesterday's curry."
```

```text
"What have I eaten today?"
```

```text
"How much protein have I had today?"
```

```text
"Pull up my curry recipe."
```

```text
"What did I think about it last time?"
```

```text
"I cooked this again and got eight portions."
```

If those interactions work exceptionally well, V1 succeeds.

---

# 26. Suggested database model

Start around these entities:

```text
food
food_nutrition
food_alias

recipe
recipe_version
recipe_ingredient

cook_event
food_batch

consumption_event

note

attachment

source
```

Potential relationship:

```text
Recipe
  │
  └── RecipeVersion
         │
         ├── RecipeIngredients → Food
         │
         └── CookEvent
                │
                └── FoodBatch
                       │
                       └── ConsumptionEvent
```

A consumption event can alternatively directly reference a food.

---

# 27. The most important architectural rule

Keep this boundary clean:

```text
              ┌───────────────┐
              │      LLM      │
              └───────┬───────┘
                      │
                 semantic intent
                      │
              ┌───────▼───────┐
              │ MCP / Agent   │
              │     tools     │
              └───────┬───────┘
                      │
               deterministic API
                      │
              ┌───────▼───────┐
              │ Domain layer  │
              └───────┬───────┘
                      │
                 persistence
                      │
              ┌───────▼───────┐
              │  PostgreSQL   │
              └───────────────┘
```

The agent determines:

> "Fabian means one portion of batch #123."

The backend determines:

> "What does consuming one portion of batch #123 mean?"

That separation will save enormous amounts of pain later.

---

# 28. Development plan

I would build this vertically rather than database-first.

**Milestone 1 — Core food log**

Get this working:

```text
POST consumption
GET today's consumption
GET today's nutrition
```

with manual foods.

**Milestone 2 — Recipes**

Add:

```text
recipes
versions
ingredients
calculated nutrition
```

**Milestone 3 — Meal prep**

Add:

```text
cook events
batches
portions
```

Now:

> one portion of Monday's curry

works.

**Milestone 4 — Hermes**

Connect Signal → Hermes → API.

Text first.

Then add images.

**Milestone 5 — Dashboard**

Build the mobile PWA with today's log and active batches.

**Milestone 6 — MCP**

Expose the domain tools to ChatGPT so conversational cooking and querying work.

Only after that should we add anything else.
