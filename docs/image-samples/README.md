# Meal image sample — owner approved 2026-09-30

`chicken-teriyaki-v1.png` is a single sample, generated with the built-in image generator on
2026-09-30. The owner approved it as the style anchor for the complete twelve-meal set.
Round 3 reuses this original as `frontend/public/images/meals/chicken-teriyaki-v1.webp`.

The sample represents seeded meal **Kylling teriyaki med ris**. Visual inspection checked chicken,
jasmine rice, broccoli and carrots, natural light, neutral backdrop, no text or unlisted garnishes.
It illustrates the recipe concept; it is not a photograph of an actual supplied meal or evidence
of portion weights/nutritional values. The published UI explicitly labels these images as
AI-generated illustrations in Norwegian/English; presentation may vary. Nutrition and allergens
continue to come from the catalogue data, never inferred from pixels.

## Generation prompt

Use case: photorealistic-natural. Asset type: ONE sample food photograph for the Prepwise meal
catalogue, not a collage. Subject: Kylling teriyaki med ris — a realistic single portion of cooked
boneless chicken pieces lightly coated in teriyaki sauce, white jasmine rice, steamed broccoli
florets and sliced carrot. These are the only food ingredients to depict. Scene: plain off-white
ceramic shallow bowl on a neutral warm light grey matte tabletop, natural Scandinavian window
light, soft believable shadows. Composition: landscape 4:3 food photography, three-quarter
overhead angle around 45 degrees, entire bowl visible centered with safe margins for responsive
meal-card crop; inviting practical meal-prep portion, not fine-dining styling. Medium: realistic
commercial food photography with honest texture, subtle imperfections, appetizing but not
oversaturated. Consistent quiet styling suitable for a future twelve-meal series. Avoid sesame
seeds, green onions, herbs or any unlisted garnish, cutlery, hands, extra bowls, text, logos,
labels, watermarks, packaging, extreme glossy plastic-looking food. Output exactly one clean
photograph.

## Next decision

The owner approved the sample style on 2026-09-30. Reuse it when generating the remaining
11 catalogue images in round 3. No unlimited image calls or external image API fallback is approved.

## Complete set / implementation

The built-in generator produced the remaining eleven recipes with two disjoint workers,
one call per meal, no retries or external image API. Exact prompts, original native output paths
and recipe/visual checks are in [batch A](round3-a.md) and [batch B](round3-b.md).
The entire WebP set was also inspected after encoding. Subtle seasonings/sauce constituents
and protein species cannot be established from pixels; this is illustrative imagery, not evidence
of an actual food portion, nutritional value, ingredient absence or allergen safety.

- Delivery assets: `frontend/public/images/meals/*-v1.webp`, 960 × 720, roughly 81–130 kB each.
- Encoding: existing bundled Sharp, quality 82, no crop/retouch/compositing. The script is
  `scripts/prepare-meal-images.mjs <installed-sharp-module-path>`; it requires the eleven
  source PNGs copied temporarily from the recorded native outputs into the asset directory.
  The teriyaki input remains this approved sample. No dependency was added to the application.
- Temporary source copies are removed from the public directory after verification; original
  native PNGs remain at the recorded output paths. Only delivery WebPs are shipped.
- Backend resolves a versioned frontend-relative image path for known unchanged ingredient
  sets, irrespective of language. No DB migration, catalogue backfill, reseeding or translation
  change is required. Authored image URLs take precedence; changed/unknown recipes get no
  automatic illustration. Admin responses keep the stored field (not the presentation fallback).
- Cards load lazily, detail images eagerly. Both have translated alternative text/disclosure.
  Failed images use the existing accessible placeholder; missing production assets are 404s,
  not HTML from SPA navigation fallback.
- These paths are hosted on the frontend origin, not a new API/static-file service. A backend-first
  first rollout may temporarily return new paths before the frontend upload; the previous UI
  does not have the new error fallback and can briefly show a failed image. The new UI handles
  failed assets after upload; a fresh page load receives the new bundle. Do not claim atomic
  frontend/backend deployment. A rollback needs no DB downgrade/business-data undo for this feature.
- Creative Production guided consistent styling, exact recipe grounding and two-worker generation.
  Its review-board tool was not exposed directly in this environment; native files/chat plus
  direct visual inspection were used instead. No nested board call or external API fallback.
