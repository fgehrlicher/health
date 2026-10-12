# Post-processing the USDA foods

You decide two things for each food in a batch file: its food group, and a German
name. The batch file is a JSON array. Each item has `slug`, `name` (English, from
USDA), `usda_category` (USDA's own category, a hint only) and `preparation_state`.

Write your answer as a JSON array to the decisions file named in the task. One
item per food in the batch, in any order:

```json
[
  {"slug": "usda-169997", "food_group": "G", "name_de": "Koriander, frisch (Blätter)"}
]
```

Write only the JSON array to the file. Do not add comments or other keys. Every
slug in the batch must appear exactly once.

## Food groups

Choose exactly one code. These are the catalog's groups, with the German names
they are shown under:

- B: Brot (bread, crispbread, rolls, flour-based breads)
- C: Getreide und Getreideprodukte (grains, flours, breakfast cereals, rice, oats, pasta-like grains, bran)
- D: Kuchen und Backwaren (cakes, cookies, pastries, pies, pancakes, crackers, baked goods)
- E: Eier und Nudeln (eggs and egg dishes, pasta and noodles)
- F: Obst (fruit, fruit juices, dried fruit, berries)
- G: Gemüse (vegetables, including onions, garlic, peppers, tomatoes, leafy greens, herbs used as vegetables)
- H: Hülsenfrüchte, Nüsse, Samen und Sprossen (legumes, tofu, nuts, seeds, nut butters, sprouts)
- K: Kartoffeln und Pilze (potatoes, sweet potatoes, cassava, mushrooms)
- M: Milchprodukte (milk, yogurt, cheese, cream, quark, skyr, butter-free dairy)
- N: Alkoholfreie Getränke (water, tea, coffee, soft drinks, alcohol-free beer and wine, plant milks and milk drinks without alcohol)
- P: Alkoholische Getränke (beer, wine, spirits, liqueurs, alcoholic mixed drinks)
- Q: Fette und Öle (oils, butter, lard, margarine, dressings made of fat)
- R: Gewürze und Soßen (spices, dried herbs, seasoning blends, salt, condiments, sauces, ketchup, mustard, vinegar, stock cubes)
- S: Süßwaren (sugar, honey, syrups, candy, chocolate, sweet spreads, jams, desserts that are mainly sugar)
- T: Fisch und Meeresfrüchte (fish, shellfish, seafood, fish products)
- U: Rotes Fleisch (beef, pork, lamb, veal, goat, game mammals, offal of these)
- V: Geflügel und Wild (chicken, turkey, duck, goose, other poultry, game birds, eggs excluded)
- W: Fleischwaren (processed meat: sausages, ham, bacon, salami, cold cuts, canned meat, meat spreads)
- X: Überwiegend pflanzliche Gerichte (mixed dishes that are mostly plant based: vegetable stews, bean dishes, soups made of vegetables, salads, plant-based ready meals)
- Y: Überwiegend tierische Gerichte (mixed dishes that are mostly animal based: meat or fish dishes, casseroles, sandwiches with meat, soups with meat)

Rules for choosing:

- Go by the food itself. A single ingredient belongs to its own group.
- A mixed dish belongs to X or Y by its main ingredient, unless a more specific group fits better.
- Spices, herbs used as flavouring, and salt belong to R. Fresh leafy herbs eaten as a vegetable belong to G.
- Alcohol-free beer or wine belongs to N, alcoholic ones to P.
- Use `usda_category` only when the name does not decide it.
- Do not invent a group. Every food must get one of the codes above.

## German names

- Keep the structure of the English name: the main food first, then the
  descriptors after a comma, as German food tables do. Example: "Coriander
  (cilantro) leaves, raw" becomes "Koriander, frisch (Blätter)".
- Translate the descriptors: raw → roh; cooked, boiled → gekocht; dried →
  getrocknet; frozen → tiefgefroren; canned → aus der Dose; fried → gebraten;
  baked → gebacken; roasted → geröstet; grilled → gegrillt; smoked → geräuchert;
  braised → geschmort; stewed → gedünstet. Use standard German food terms.
- Keep brand names as they are. Keep names of dishes that are known in German
  under their German name.
- Do not add facts that the English name does not give. Do not add the origin
  or the type of product unless the name says it.
- Names are short. No trailing full stop, at most 200 characters.
- Where USDA writes "NFS" (not further specified), write "o. n. A." (ohne nähere
  Angabe).
- Where the English name is a single word that is also a German word, the German
  name may be the same word, for example "Oregano, getrocknet" or "Kakao".
