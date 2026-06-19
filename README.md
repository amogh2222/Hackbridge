# 🚀 HackBridge — AI-Enabled Hackathon Management Platform

A production-grade FastAPI backend powering intelligent hackathon operations:
duplicate detection, skill extraction, optimal reviewer assignment, and bias-aware evaluation auditing.

## Architecture

```
hackbridge/
├── sql/schema.sql          # Supabase PostgreSQL + pgvector schema
├── app/
│   ├── main.py             # FastAPI app factory, CORS, middleware
│   ├── database.py         # Supabase client singleton
│   ├── models.py           # Pydantic request/response schemas
│   ├── routers/
│   │   ├── auth.py         # GoTrue auth (register/login)
│   │   ├── dashboard.py    # Organizer metrics, audit log, leaderboard
│   │   └── ai.py           # AI endpoints
│   └── services/
│       ├── skills.py       # LLM-powered skill extraction
│       ├── dedupe.py       # Fuzzy duplicate detection (rapidfuzz)
│       ├── reviewer.py     # Optimal reviewer assignment (Hungarian algo)
│       └── bias.py         # Z-score bias detection
├── seed.py                 # Faker-based demo data with injected anomalies
├── requirements.txt
├── .env.example
└── README.md
```

## Quick Start

### 1. Database Setup

1. Create a new [Supabase](https://supabase.com) project.
2. Go to **SQL Editor** and run the contents of `sql/schema.sql`.

### 2. Environment Variables

```bash
cp .env.example .env
# Edit .env with your Supabase URL, key, and OpenAI API key
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Seed Demo Data

```bash
python seed.py
```

This creates 50 participants, 10 judges, 15 projects, evaluations, and **intentionally injects**:
- 2 duplicate user registrations (for dedupe demo)
- 1 biased judge with abnormally low scores (for bias detection demo)

### 5. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register via GoTrue |
| `POST` | `/api/auth/login` | Login, receive JWT |
| `GET`  | `/api/dashboard/organizer` | Aggregated platform metrics |
| `GET`  | `/api/dashboard/audit-log` | Full transparency audit trail |
| `GET`  | `/api/dashboard/leaderboard/{id}` | Bias-aware project rankings |
| `POST` | `/api/ai/extract-skills` | LLM skill extraction from bio |
| `POST` | `/api/ai/dedupe` | Fuzzy duplicate detection |
| `POST` | `/api/ai/assign-reviewers` | Optimal judge↔project matching |
| `POST` | `/api/ai/detect-bias` | Z-score evaluation auditing |

## AI Features

### 🔍 Duplicate Detection
Uses `rapidfuzz` token-sort-ratio with weighted composite scoring (40% name + 60% email). Threshold: 85%.

### 🧠 Skill Extraction
LLM-powered (via `litellm`) extraction of technical skills from free-text bios. Returns clean JSON arrays.

### 🎯 Reviewer Assignment
Embeds project descriptions and judge expertise with `sentence-transformers/all-MiniLM-L6-v2`. Solves the assignment problem using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) with a hard constraint of ≤5 projects per judge.

### ⚖️ Bias Detection
Computes per-project Z-scores for judge evaluations. Flags anomalies at |Z| > 2σ and writes to the immutable audit log.

## Performance Targets

| Metric | Target | Method |
|--------|--------|--------|
| Deduplication accuracy | 95% | Fuzzy string matching |
| Skill extraction accuracy | 85% | LLM with structured prompting |
| Assignment match accuracy | 90% | Cosine similarity + Hungarian algorithm |
| 100+ projects processing | <60s | Vectorized numpy operations |

## Tech Stack

- **FastAPI** — async Python web framework
- **Supabase** — PostgreSQL + pgvector + GoTrue Auth
- **LiteLLM** — unified LLM API gateway
- **sentence-transformers** — local embedding generation
- **scipy** — linear assignment optimization
- **rapidfuzz** — high-performance fuzzy string matching
- **Faker** — realistic mock data generation
