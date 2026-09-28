# Vision

A personal, self-hosted system that becomes my source of truth for what I eat
and cook: foods and products, meals, recipes and how they evolve, meal-prep
batches, and eventually other health signals. It is for one person: me.

This document describes the idea, not the design. Concrete decisions are made
as the system grows and are documented in [Current state](current-state.md).

## Why

Tracking food has helped me before, but calorie-tracking apps eventually fail:
entering data is too much work, and missing one meal turns into missing a week.

The goal is therefore **not perfect tracking**. The goal is:

> Make capturing useful health data so frictionless that incomplete tracking is
> still worth doing.

A day with 70% of meals captured is valuable. A meal logged as "unknown" is
better than a meal not logged at all.

## How it should feel

I tell the system what happened, the way I would tell a person, and it turns
that into structured records:

> [photo of a package] Eating this now.

> I had one portion of Monday's curry.

> I cooked the curry again, but with 600 g chicken instead of 500 g. It made
> nine portions.

> Actually that was yesterday, not today.

And I can ask:

> What have I eaten today? How much protein was that?

> Pull up my curry recipe. What did I change last time?

The agent asks only when the answer would meaningfully change the result, and
corrections are as easy as the original entry. If I can go weeks without opening
a traditional calorie-tracking app, the system works.

## Core ideas

**Capture first, structure second.** Text, voice, photos, and barcodes are all
valid input. The work of structuring them belongs to the system, not to me.

**Honest numbers.** Every value comes from real data: a food database, a
product label, a weighed amount. When something is estimated or unknown, the
system says so instead of inventing a precise-looking number.

**The agent interprets; the backend decides.** An agent understands what I
mean ("one portion of Monday's curry"). A deterministic backend decides what
that means for the data and enforces the rules. Agents never write to the
database directly.

**One backend, many ways in.** Chat, messengers, a small dashboard on my phone,
and future tools all use the same API, so the rules live in one place.

**My own recorded intent.** For recipes, the system remembers what I cooked,
what I changed, and what I wanted to do differently next time. It does not
invent recommendations of its own.

**Private by default.** It runs on my own hardware and holds my data only.

## Not the point

Medical advice, diet coaching, meal recommendations, multi-user support, and
large analytics platforms. Some of these may become interesting later; none of
them is why this exists.
