# Prepwise assistant evaluation dataset

`assistant_cases.jsonl` is the version-controlled source of truth for assistant evaluations.
Each line is one independent case validated by `prepwise_api.assistant_evals`.

The dataset deliberately separates:

- setup state such as cart contents, existing orders and confirmations;
- expected tool selection and exact stable arguments;
- response facts, knowledge sources and meal constraints;
- expected cart, confirmation and order side effects.

Dynamic values use templates. `{{confirmation_phrase}}` is replaced by a server-issued phrase
during setup, and meal/cart identifiers are resolved from stable meal names by the eval runner.

Add new cases when production failures or blind spots are discovered. IDs must remain stable so
results can be compared across prompt and model versions.

## Run the suite

From `backend`, with `OPENAI_API_KEY` available:

```powershell
prepwise-eval-assistant
```

This sends the selected eval messages and the repository knowledge-base chunks to the configured
OpenAI API and incurs normal model/embedding usage. Do not add secrets or personal data to either.

Useful focused runs:

```powershell
prepwise-eval-assistant --case-id nutrition_protein_calorie_filter
prepwise-eval-assistant --category rag_questions
prepwise-eval-assistant --limit 5
```

Each case gets a fresh seeded SQLite database. The runner uses the configured Responses API model
and embedding model, and retrieves the real Markdown knowledge chunks in memory. It records every
tool call, arguments, result, response, state delta, score and failure in a JSON report under
`backend/eval-results/` (ignored by Git).

Compare a changed model or prompt against an earlier report:

```powershell
prepwise-eval-assistant --baseline eval-results/<earlier-report>.json
```

Reports include model/reasoning configuration plus SHA-256 fingerprints for the prompt and dataset.
`--fail-under 0.90` makes the command return a failing exit code when the mean score is lower.
