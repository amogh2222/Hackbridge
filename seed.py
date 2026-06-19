"""
seed.py
───────
HackBridge Database Seeding Script.

Populates Supabase with realistic demo data for the HackBridge 2026
hackathon platform. Designed to exercise every AI service module:

  • Skill extraction  → participants have rich free-text bios
  • Deduplication     → two pairs of near-duplicate users are injected
  • Reviewer assignment → judges have diverse, realistic skill sets
  • Bias detection    → one judge ("Dr. Harsh Critic") gives abnormally
                         low scores that should trigger Z-score flags

─────────────────────────────────────────────────────────────────────────
CRITICAL INJECTIONS (for demo / testing purposes)
─────────────────────────────────────────────────────────────────────────

1. DUPLICATE PAIR #1:
   "Rahul Sharma"  (rahul.sharma@gmail.com)  and
   "Rahul K Sharma" (rahul.ksharma@gmail.com)
   → Same person, slight name variation + dot-insertion in email.
   → Should be caught by the dedupe service (composite ≈ 88%).

2. DUPLICATE PAIR #2:
   "Priya Patel"    (priya.patel@outlook.com)  and
   "Priyanka Patel" (priyanka.patel@outlook.com)
   → Name prefix match + very similar email.
   → Should be caught by the dedupe service (composite ≈ 86%).

3. BIASED JUDGE:
   "Dr. Harsh Critic" gives scores in the 15–30 range while all other
   judges score between 70–95.
   → Should produce |z| > 2 for every evaluation, triggering bias flags.

─────────────────────────────────────────────────────────────────────────
USAGE:
   python seed.py
   (requires SUPABASE_URL and SUPABASE_KEY in .env)

NOTE: Since Supabase Auth (GoTrue) is separate, we insert directly into
the `users` table for seeding. In production, users would be created
through the auth flow and the `users` table would be populated via a
trigger / webhook.
─────────────────────────────────────────────────────────────────────────
"""

import os
import random
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from faker import Faker
from supabase import create_client, Client

# ─── Load environment ────────────────────────────────────────────────────────
load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
fake = Faker()
Faker.seed(42)  # Reproducible fake data
random.seed(42)

# ─── Curated list of ~30 real tech skills ─────────────────────────────────────
# Used to generate realistic participant skill sets and judge expertise.
TECH_SKILLS: list[str] = [
    "Python", "JavaScript", "TypeScript", "React", "Next.js",
    "Node.js", "FastAPI", "Django", "Flask", "Go",
    "Rust", "Java", "Kotlin", "Swift", "C++",
    "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure",
    "PostgreSQL", "MongoDB", "Redis", "GraphQL", "REST APIs",
    "LangChain", "OpenAI API", "Hugging Face", "Computer Vision",
]

# ─── Bio templates for realistic participant descriptions ─────────────────────
BIO_TEMPLATES: list[str] = [
    "Full-stack developer with {years}+ years of experience in {s1} and {s2}. "
    "Passionate about {s3} and building scalable web applications.",

    "ML engineer specializing in {s1} and {s2}. Currently exploring {s3} "
    "for production deployments. Love hackathons and open-source.",

    "Computer science student at {university}. Experienced with {s1}, {s2}, "
    "and {s3}. Looking to build impactful projects using AI.",

    "Backend engineer at a fintech startup. Daily driver: {s1}, {s2}. "
    "Side projects in {s3}. Keen on system design and distributed systems.",

    "Data scientist with expertise in {s1}, {s2}, and {s3}. Published "
    "research on NLP and recommendation systems. {years}+ years in industry.",

    "DevOps engineer proficient in {s1}, {s2}, and {s3}. Certified cloud "
    "architect. Interested in infrastructure-as-code and CI/CD pipelines.",

    "Mobile developer building cross-platform apps with {s1}. Backend "
    "experience with {s2} and {s3}. Hackathon winner at HackMIT 2025.",
]

UNIVERSITIES: list[str] = [
    "IIT Bombay", "Stanford", "MIT", "IIT Delhi", "Carnegie Mellon",
    "UC Berkeley", "NIT Trichy", "BITS Pilani", "Georgia Tech", "ETH Zurich",
]

# ─── Project descriptions for realistic hackathon entries ─────────────────────
PROJECT_TEMPLATES: list[dict] = [
    {"title": "MediScan AI", "desc": "An AI-powered medical image analysis platform that uses deep learning to detect anomalies in X-rays and MRIs, helping radiologists prioritise urgent cases."},
    {"title": "EcoTrack", "desc": "Real-time carbon footprint tracker that integrates with banking APIs to calculate the environmental impact of everyday purchases using ML classification."},
    {"title": "CodeMentor", "desc": "LLM-powered code review assistant that provides contextual feedback, detects anti-patterns, and suggests optimisations for Python and JavaScript codebases."},
    {"title": "AgriDrone", "desc": "Computer vision system for agricultural drones that identifies crop diseases, estimates yield, and generates precision farming recommendations."},
    {"title": "SafeRoute", "desc": "ML-based navigation app that analyses crime data, lighting conditions, and pedestrian traffic to recommend the safest walking routes in urban areas."},
    {"title": "LinguaBridge", "desc": "Real-time multilingual meeting translator using speech recognition and neural machine translation, supporting 20+ languages with sub-second latency."},
    {"title": "FinGuard", "desc": "Fraud detection engine for digital payments using graph neural networks to identify suspicious transaction patterns in real-time."},
    {"title": "StudyBuddy", "desc": "Adaptive learning platform that uses spaced repetition algorithms and NLP to generate personalised quiz questions from uploaded lecture notes."},
    {"title": "GreenGrid", "desc": "Smart energy management system for buildings using IoT sensors and reinforcement learning to optimise HVAC and lighting for minimum energy waste."},
    {"title": "AccessiWeb", "desc": "Browser extension powered by computer vision that automatically generates alt-text for images and improves web accessibility for visually impaired users."},
    {"title": "ThreatLens", "desc": "Cybersecurity dashboard that uses NLP to parse threat intelligence feeds and correlate indicators of compromise across an organisation's infrastructure."},
    {"title": "FarmConnect", "desc": "Marketplace platform connecting small-scale farmers directly with consumers, using demand prediction ML models to reduce food waste."},
    {"title": "HealthPulse", "desc": "Wearable data analytics platform that uses time-series forecasting to predict health anomalies and alert users before symptoms manifest."},
    {"title": "UrbanPlan AI", "desc": "City planning tool that uses satellite imagery analysis and population flow simulation to optimise public transport routes and urban infrastructure."},
    {"title": "VoiceAuth", "desc": "Speaker verification system using deep audio embeddings for secure, passwordless authentication in banking and enterprise applications."},
]

TEAM_NAMES: list[str] = [
    "Neural Knights", "Byte Busters", "Code Crusaders", "Data Dynamos",
    "Pixel Pirates", "Algo Avengers", "Cloud Catalysts", "Hack Hawks",
    "Binary Blazers", "Quantum Coders", "Stack Smashers", "Debug Dragons",
    "API Architects", "Lambda Lords", "Git Guardians",
]


def _gen_id() -> str:
    """Generate a UUID4 string for use as a primary key."""
    return str(uuid.uuid4())


def _random_skills(min_k: int = 3, max_k: int = 7) -> list[str]:
    """Pick a random subset of tech skills."""
    k = random.randint(min_k, max_k)
    return random.sample(TECH_SKILLS, k)


def _gen_bio(skills: list[str]) -> str:
    """Generate a realistic tech bio from a template and skills."""
    template = random.choice(BIO_TEMPLATES)
    return template.format(
        s1=skills[0],
        s2=skills[1],
        s3=skills[2] if len(skills) > 2 else skills[0],
        years=random.randint(1, 8),
        university=random.choice(UNIVERSITIES),
    )


def main() -> None:
    """Seed the database with demo data."""
    now = datetime.now(timezone.utc).isoformat()

    # ═══════════════════════════════════════════════════════════════════════
    # 0. CLEANUP — wipe existing data so the script is idempotent
    # ═══════════════════════════════════════════════════════════════════════
    print("🧹 Cleaning existing data...")
    for table in ["evaluations", "project_assignments", "audit_log", "projects", "hackathons", "users"]:
        try:
            sb.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        except Exception as e:
            print(f"  ⚠️  Could not clear {table}: {e}")
    print("✅ Tables cleaned")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. ADMIN USER
    # ═══════════════════════════════════════════════════════════════════════
    admin_id = _gen_id()
    admin = {
        "id": admin_id,
        "email": "amogh@hackbridge.dev",
        "first_name": "Amogh",
        "last_name": "Srivastava",
        "role": "admin",
        "skills": ["Platform Architecture", "FastAPI", "Supabase", "React"],
        "bio": "Creator of HackBridge. Full-stack engineer passionate about developer tools and hackathon culture.",
        "created_at": now,
    }
    sb.table("users").insert(admin).execute()
    print(f"✅ Admin created: {admin['first_name']} {admin['last_name']}")

    # ═══════════════════════════════════════════════════════════════════════
    # 2. PARTICIPANTS (50 regular + 4 critical injection duplicates)
    # ═══════════════════════════════════════════════════════════════════════
    participant_ids: list[str] = []

    for _ in range(50):
        pid = _gen_id()
        participant_ids.append(pid)
        skills = _random_skills()
        participant = {
            "id": pid,
            "email": fake.unique.email(),
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "role": "participant",
            "skills": skills,
            "bio": _gen_bio(skills),
            "created_at": now,
        }
        sb.table("users").insert(participant).execute()

    print(f"✅ {len(participant_ids)} participants created")

    # ─── CRITICAL INJECTION: Duplicate Pair #1 ────────────────────────────
    # "Rahul Sharma" and "Rahul K Sharma" — same person, slight name
    # variation and a dot-insertion in the email local part.
    # The dedupe service should flag these as a match (composite ≈ 88%).
    dup1a_id = _gen_id()
    dup1b_id = _gen_id()
    dup1_skills = ["Python", "React", "TensorFlow", "Docker"]

    dup1a = {
        "id": dup1a_id,
        "email": "rahul.sharma@gmail.com",
        "first_name": "Rahul",
        "last_name": "Sharma",
        "role": "participant",
        "skills": dup1_skills,
        "bio": "ML engineer with 3 years of experience in Python and TensorFlow. Love building computer vision models.",
        "created_at": now,
    }
    dup1b = {
        "id": dup1b_id,
        "email": "rahul.ksharma@gmail.com",
        "first_name": "Rahul K",
        "last_name": "Sharma",
        "role": "participant",
        "skills": dup1_skills,
        "bio": "Machine learning engineer specializing in Python, TensorFlow, and computer vision applications.",
        "created_at": now,
    }
    sb.table("users").insert(dup1a).execute()
    sb.table("users").insert(dup1b).execute()
    print("✅ Duplicate pair #1 injected: Rahul Sharma ↔ Rahul K Sharma")

    # ─── CRITICAL INJECTION: Duplicate Pair #2 ────────────────────────────
    # "Priya Patel" and "Priyanka Patel" — name prefix match with very
    # similar email local parts. Tests the token_sort_ratio's ability to
    # catch partial name overlaps combined with email similarity.
    dup2a_id = _gen_id()
    dup2b_id = _gen_id()
    dup2_skills = ["JavaScript", "React", "Node.js", "MongoDB"]

    dup2a = {
        "id": dup2a_id,
        "email": "priya.patel@outlook.com",
        "first_name": "Priya",
        "last_name": "Patel",
        "role": "participant",
        "skills": dup2_skills,
        "bio": "Frontend developer passionate about React and modern JavaScript. Building accessible web apps.",
        "created_at": now,
    }
    dup2b = {
        "id": dup2b_id,
        "email": "priyanka.patel@outlook.com",
        "first_name": "Priyanka",
        "last_name": "Patel",
        "role": "participant",
        "skills": dup2_skills,
        "bio": "Full-stack JS developer with React, Node.js, and MongoDB experience. Open-source contributor.",
        "created_at": now,
    }
    sb.table("users").insert(dup2a).execute()
    sb.table("users").insert(dup2b).execute()
    print("✅ Duplicate pair #2 injected: Priya Patel ↔ Priyanka Patel")

    # ═══════════════════════════════════════════════════════════════════════
    # 3. JUDGES (9 regular + 1 biased "Dr. Harsh Critic")
    # ═══════════════════════════════════════════════════════════════════════
    judge_ids: list[str] = []
    judge_names: list[str] = []

    # Regular judges with diverse skill sets
    judge_profiles = [
        ("Dr. Ananya", "Krishnan",  ["Python", "TensorFlow", "Computer Vision", "PyTorch"]),
        ("Prof. James", "Chen",     ["JavaScript", "React", "Node.js", "GraphQL"]),
        ("Dr. Fatima", "Al-Rashid", ["AWS", "Docker", "Kubernetes", "Go"]),
        ("Prof. Marcus", "Weber",   ["Java", "Kotlin", "Android", "REST APIs"]),
        ("Dr. Yuki", "Tanaka",      ["Python", "Pandas", "Scikit-learn", "NumPy"]),
        ("Prof. Elena", "Volkov",   ["Rust", "C++", "Systems Programming", "Redis"]),
        ("Dr. Kwame", "Asante",     ["FastAPI", "PostgreSQL", "Django", "Docker"]),
        ("Prof. Sarah", "Mitchell", ["LangChain", "OpenAI API", "Hugging Face", "Python"]),
        ("Dr. Raj", "Mehta",        ["GCP", "Azure", "Kubernetes", "MongoDB"]),
    ]

    for first, last, skills in judge_profiles:
        jid = _gen_id()
        judge_ids.append(jid)
        judge_names.append(f"{first} {last}")
        judge = {
            "id": jid,
            "email": f"{first.lower().replace('.', '').replace(' ', '')}.{last.lower()}@hackbridge.dev",
            "first_name": first,
            "last_name": last,
            "role": "judge",
            "skills": skills,
            "bio": f"Industry expert and hackathon judge with deep expertise in {', '.join(skills[:3])}.",
            "created_at": now,
        }
        sb.table("users").insert(judge).execute()

    # ─── CRITICAL INJECTION: Biased Judge ─────────────────────────────────
    # "Dr. Harsh Critic" gives abnormally low scores (15–30) to ALL
    # projects. When other judges score 70–95, this creates a strong
    # negative Z-score (|z| > 2) that the bias detection service should
    # catch and flag.
    biased_judge_id = _gen_id()
    judge_ids.append(biased_judge_id)
    judge_names.append("Dr. Harsh Critic")
    biased_judge = {
        "id": biased_judge_id,
        "email": "harsh.critic@hackbridge.dev",
        "first_name": "Dr. Harsh",
        "last_name": "Critic",
        "role": "judge",
        "skills": ["Python", "JavaScript", "Code Review", "Security"],
        "bio": "Senior software architect with extremely high standards. 20+ years in industry. Known for rigorous code reviews.",
        "created_at": now,
    }
    sb.table("users").insert(biased_judge).execute()
    print(f"✅ {len(judge_ids)} judges created (including Dr. Harsh Critic 🎭)")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. HACKATHON
    # ═══════════════════════════════════════════════════════════════════════
    hackathon_id = _gen_id()
    hackathon = {
        "id": hackathon_id,
        "title": "HackBridge 2026",
        "description": "The flagship HackBridge hackathon — 48 hours of innovation, collaboration, and impact. Open to developers, designers, and data scientists worldwide.",
        "status": "active",
        "start_time": "2026-07-15T09:00:00Z",
        "end_time": "2026-07-17T09:00:00Z",
        "created_at": now,
    }
    sb.table("hackathons").insert(hackathon).execute()
    print(f"✅ Hackathon created: {hackathon['title']} ({hackathon_id})")

    # ═══════════════════════════════════════════════════════════════════════
    # 5. PROJECTS (15 projects linked to the hackathon)
    # ═══════════════════════════════════════════════════════════════════════
    project_ids: list[str] = []

    for i, tmpl in enumerate(PROJECT_TEMPLATES):
        proj_id = _gen_id()
        project_ids.append(proj_id)

        # Assign 2–4 random participants as team members
        team_member_ids = random.sample(participant_ids, random.randint(2, 4))

        project = {
            "id": proj_id,
            "hackathon_id": hackathon_id,
            "title": tmpl["title"],
            "description": tmpl["desc"],
            "team_name": TEAM_NAMES[i],
            "tech_stack": _random_skills(3, 5),
            "created_at": now,
        }
        sb.table("projects").insert(project).execute()

    print(f"✅ {len(project_ids)} projects created")

    # ═══════════════════════════════════════════════════════════════════════
    # 6. EVALUATIONS
    #    Each judge evaluates 3–5 projects with realistic scores.
    #    Dr. Harsh Critic uses abnormally low scores (15–30).
    # ═══════════════════════════════════════════════════════════════════════
    eval_count = 0

    for judge_id in judge_ids:
        # Each judge evaluates a random subset of 3–5 projects
        n_reviews = random.randint(3, 5)
        reviewed_projects = random.sample(project_ids, n_reviews)

        for proj_id in reviewed_projects:
            # ── Score generation ──────────────────────────────────────────
            # Regular judges: realistic scores in the 70–95 range
            # Biased judge:   abnormally low scores in the 15–30 range
            # This differential is what the bias detection Z-score analysis
            # should catch — Dr. Harsh Critic's scores will be >2σ below
            # the per-project mean.
            if judge_id == biased_judge_id:
                # BIASED: abnormally low scores (15-30 range out of 100)
                innovation = random.randint(15, 30)
                technical = random.randint(15, 30)
                presentation = random.randint(15, 30)
                impact = random.randint(15, 30)
            else:
                # NORMAL: realistic high-quality hackathon scores (70-95 range out of 100)
                innovation = random.randint(70, 95)
                technical = random.randint(70, 95)
                presentation = random.randint(70, 95)
                impact = random.randint(70, 95)

            evaluation = {
                "id": _gen_id(),
                "hackathon_id": hackathon_id,
                "project_id": proj_id,
                "judge_id": judge_id,
                "score_innovation": innovation,
                "score_technical": technical,
                "score_business": impact,
                "score_presentation": presentation,
                "feedback": fake.sentence(nb_words=12),
                "bias_flag": False,
                "created_at": now,
            }
            sb.table("evaluations").insert(evaluation).execute()
            eval_count += 1

    print(f"✅ {eval_count} evaluations created")

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 60)
    print("  🌉 HackBridge Seed Complete!")
    print("═" * 60)
    print(f"  Admin:          1  (Amogh Srivastava)")
    print(f"  Participants:   54 (50 regular + 4 duplicate injections)")
    print(f"  Judges:         {len(judge_ids)} ({len(judge_ids) - 1} regular + 1 biased)")
    print(f"  Hackathon:      1  (HackBridge 2026)")
    print(f"  Projects:       {len(project_ids)}")
    print(f"  Evaluations:    {eval_count}")
    print("─" * 60)
    print("  🧪 Test Injections:")
    print(f"    • Duplicate #1: Rahul Sharma ↔ Rahul K Sharma")
    print(f"    • Duplicate #2: Priya Patel  ↔ Priyanka Patel")
    print(f"    • Biased Judge: Dr. Harsh Critic (scores 15–30)")
    print("─" * 60)
    print(f"  Hackathon ID: {hackathon_id}")
    print(f"  Use this ID for /api/ai/assign-reviewers and /api/ai/detect-bias")
    print("═" * 60)


if __name__ == "__main__":
    main()
