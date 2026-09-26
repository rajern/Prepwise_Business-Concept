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
