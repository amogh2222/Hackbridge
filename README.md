<div align="center">
  <h1>🌉 HackBridge</h1>
  <p><b>An AI-Powered, Optimization-Driven Hackathon Operating System</b></p>
</div>

---

## 📖 Overview
HackBridge is an intelligent hackathon management platform that replaces tedious manual logistics with Agentic AI and mathematical optimization. 

> **Technical Highlights:** Demonstrates applied use of the **Hungarian Optimization Algorithm** for bipartite matching, **fuzzy string matching** for data sanitization, and **Generative AI (Gemini 2.0)** for unstructured data parsing within an asynchronous **FastAPI** backend.

---

## 🏗️ System Architecture

~~~mermaid
graph LR
    UI[Frontend Client] --> API(FastAPI Gateway)
    API --> DB[Supabase PostgreSQL]
    
    API -.-> Dedupe[Fuzzy Deduplication]
    API -.-> Skills[LLM Skill Extractor]
    API -.-> Assign[Hungarian Assignment]
    API -.-> Bias[Z-Score Bias Detection]
~~~

## ✨ Core Engineering Features

1. **Bipartite Reviewer Optimization:** Converts project descriptions and judge bios into dense vector embeddings (`all-MiniLM-L6-v2`). Computes a cosine similarity matrix and applies the **Hungarian Algorithm** to mathematically guarantee optimal judge-to-project assignments.
2. **Generative Skill Extraction:** Streams natural language user bios through **Google Gemini 2.0 Flash** to intelligently parse and extract structured, validated technical skills (JSON).
3. **Intelligent Deduplication:** Uses `RapidFuzz` to compute Levenshtein distance-based confidence scores in real-time, preventing duplicate registrations.
4. **Statistical Bias Detection:** Dynamically calculates Z-Scores (Z > 2.0) across all evaluation metrics to autonomously flag statistically anomalous grading behaviors by judges.

---

## 🛠️ Technology Stack
* **Backend:** FastAPI, Python 3.11+, Uvicorn
* **Database:** Supabase (PostgreSQL)
* **AI & Machine Learning:** Google Gemini (`litellm`), `sentence-transformers`, `scipy`, `numpy`, `rapidfuzz`

---

## 🚀 Quick Start (Local Setup)

1. **Clone & Setup Environment**
~~~bash
git clone https://github.com/YOUR_USERNAME/hackbridge-ai.git
cd hackbridge
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Mac/Linux
pip install -r requirements.txt
~~~

2. **Configure Environment (.env)**
Create a `.env` file in the root directory and add:
~~~ini
SUPABASE_URL="your_supabase_url"
SUPABASE_KEY="your_supabase_anon_key"
GEMINI_API_KEY="your_gemini_api_key"
~~~

3. **Launch Application**
~~~bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
~~~
Navigate to `http://localhost:8000/` to access the UI, or `http://localhost:8000/docs` for the Swagger API documentation.
