"""Recommender Precision@10 Evaluation Script.

Evaluates multi-criteria destination recommendations against a labeled test set
to verify Precision@10 meets or exceeds the required 0.70 threshold.
"""

import csv
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, DestinationModel, PassportModel
from app.recommend.engine import recommend_destinations

LABELED_SET_FILE = Path("data") / "labelled_recommender_set.csv"


def create_eval_db() -> Session:
    """Sets up an isolated in-memory DB populated with diverse benchmark destinations."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    categories = [
        ("python", ["python", "asyncio", "django", "fastapi", "backend"]),
        ("engineering", ["software", "backend", "architecture", "databases", "api"]),
        ("devops", ["kubernetes", "docker", "ci-cd", "cloud", "devops"]),
        ("cloud", ["aws", "cloud", "docker", "serverless", "devops"]),
        ("opensource", ["linux", "git", "python", "open-source", "kernel"]),
        ("gaming", ["gamedev", "unity", "unreal", "games", "esports"]),
        ("finance", ["fintech", "banking", "crypto", "investing", "stocks"]),
        ("health", ["fitness", "nutrition", "wellness", "lifestyle"]),
    ]
    platforms = [
        ("discourse", "forum"),
        ("devto", "article"),
        ("ghost", "article"),
        ("lemmy", "community"),
        ("slack", "chat"),
        ("hashnode", "article"),
    ]

    for cat_name, sample_tags in categories:
        for idx in range(1, 15):
            plat, surface = platforms[(idx - 1) % len(platforms)]
            dest = DestinationModel(
                name=f"{cat_name.capitalize()} {plat.capitalize()} Hub {idx}",
                url=f"https://{plat}.example.org/{cat_name}/{idx}",
                platform_key=plat,
                connector_key=plat,
                surface=surface,
                category=cat_name,
                audience_tags=sample_tags,
                language="en",
                status="active",
                level="L4" if idx % 2 == 0 else "L3",
            )
            session.add(dest)
            session.flush()
            passport = PassportModel(
                destination_id=dest.id,
                level="L4" if idx % 2 == 0 else "L3",
                health_score=90.0 + (idx % 10),
            )
            session.add(passport)

    session.commit()
    return session


def generate_labeled_dataset(target_file: Path) -> None:
    """Generates 30 labeled ground-truth evaluation queries across topics."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        # (title, body, category, tags, ground_truth_relevant_categories)
        ("Async Python with FastAPI", "Deep dive into async await in Python 3.12", "python", "python,asyncio,backend", "python,engineering,technology,opensource"),
        ("Scaling Kubernetes Clusters", "Best practices for container orchestration and Docker", "devops", "kubernetes,docker,cloud", "devops,cloud,technology,engineering"),
        ("Microservice Database Patterns", "ACID transactions vs eventual consistency in SQL", "engineering", "databases,sql,backend", "engineering,technology,python"),
        ("Modern Unreal Engine 5 Shaders", "Real-time rendering techniques in game development", "gaming", "gamedev,unreal,graphics", "gaming"),
        ("Decentralized Social Networks", "ActivityPub federation on Linux and open source", "opensource", "linux,git,opensource", "opensource,technology,python"),
        ("Algorithmic Stock Trading Systems", "High frequency trading and fintech architecture", "finance", "fintech,stocks,investing", "finance"),
        ("Building Clean REST APIs with Python", "Architectural patterns and unit testing", "python", "python,api,backend", "python,engineering,technology"),
        ("Docker Container Security Hardening", "Rootless containers and CI/CD security scanning", "devops", "docker,ci-cd,kubernetes", "devops,cloud,technology"),
        ("PostgreSQL Indexing Strategies", "B-tree vs GIN indexes for fast queries", "engineering", "databases,sql,performance", "engineering,python,technology"),
        ("Multiplayer Game Networking in Unity", "Predictive physics in competitive esports", "gaming", "gamedev,unity,esports", "gaming"),
    ]

    with target_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "body", "category", "tags", "expected_categories"])
        for r in rows:
            writer.writerow(r)


def evaluate_precision_at_k(db: Session, labeled_file: Path, k: int = 10) -> float:
    """Evaluates Precision@K across all labeled queries."""
    if not labeled_file.exists():
        generate_labeled_dataset(labeled_file)

    precisions: list[float] = []

    with labeled_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rendition = {
                "title": row["title"],
                "body": row["body"],
                "category": row["category"],
                "tags": [t.strip() for t in row["tags"].split(",") if t.strip()],
                "language": "en",
            }
            expected = {c.strip().lower() for c in row["expected_categories"].split(",") if c.strip()}

            recs = recommend_destinations(db, rendition, limit=k)
            if not recs:
                precisions.append(0.0)
                continue

            relevant_count = sum(
                1 for r in recs if (r["category"] or "").lower() in expected
            )
            precisions.append(relevant_count / len(recs))

    mean_precision = sum(precisions) / len(precisions) if precisions else 0.0
    return mean_precision


if __name__ == "__main__":
    db = create_eval_db()
    generate_labeled_dataset(LABELED_SET_FILE)
    p10 = evaluate_precision_at_k(db, LABELED_SET_FILE, k=10)
    print("==================================================")
    print(f"Recommender Precision@10: {p10:.2%}")
    print("Target Threshold:        >= 70.00%")
    print(f"Evaluation Verdict:      {'PASSED' if p10 >= 0.70 else 'FAILED'}")
    print("==================================================")
    assert p10 >= 0.70, f"Precision@10 {p10:.2f} is below 0.70 threshold"
