# Prepwise

A production-ready meal-prep ordering application with an AI assistant.

**[Open the live application](https://nice-island-080f30a0f.6.azurestaticapps.net/)**

> Portfolio project and business concept — not a commercial meal-prep service.

## Features

Customers can:

- Browse meals and nutrition information
- View ingredients and allergens
- Create an account and sign in
- Manage a persistent shopping cart
- Select a pickup location
- Place and review orders
- Use an AI assistant

A protected admin interface supports managing meals, pickup locations and orders.

## Try the AI assistant

Create an account or sign in, then try:

- `Find meals with at least 40 g of protein and under 800 kcal.`
- `Add one chicken teriyaki with rice to my cart.`
- `How should I reheat a Prepwise meal?`
- `Which allergens are in the tofu satay with rice noodles?`

The assistant supports English and Norwegian and normally replies in the same language as the user.

Cart and order actions use validated application tools. Creating an order requires separate confirmation.

## AI features

- OpenAI Responses API
- Tool calling for meals, carts, orders and pickup locations
- RAG over a curated knowledge base
- PostgreSQL and pgvector retrieval
- Multi-step workflows
- Write-operation safeguards
- End-to-end AI tracing
- Automated AI evaluations

Final evaluation: **32/32 cases passed with a 0.997 mean score.**

## Architecture

```text
React + TypeScript
        ↓
FastAPI + OpenAI
        ↓
PostgreSQL + pgvector
```

Production uses:

- Azure Static Web Apps
- Azure Container Apps
- Neon PostgreSQL
- Microsoft Entra External ID
- Azure Key Vault
- Azure Monitor
- GitHub Actions

## Technology

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL, Neon, pgvector
- **AI:** OpenAI Responses API, tool calling, embeddings and RAG
- **Cloud:** Azure, Docker, Bicep and GitHub Actions
**Testing:** pytest, Vitest and Playwright

## Verification

- 100 backend tests
- Frontend tests
- Critical browser tests
- Authentication and authorization tests
- Automated AI evaluations
- Production smoke tests
- CI/CD deployment
- AI and database tracing

## Run locally

Requirements:

- Node.js 22+
- Python 3.11+
- Docker Desktop
- OpenAI API key for AI features

Start the backend and database:

```powershell
docker compose up --build -d
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python -m prepwise_api.seed
```

Start the frontend:

```powershell
cd frontend
corepack enable
pnpm install
Copy-Item .env.example .env.local
pnpm dev
```

Open `http://localhost:3000`.

## Documentation

- [Product](./PRODUCT.md)
- [Architecture](./ARCHITECTURE.md)
- [Technical decisions](./DECISIONS.md)
- [Roadmap](./ROADMAP.md)
- [Tasks](./TASKS.md)
