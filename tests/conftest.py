from __future__ import annotations

import copy
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


_MINIMAL = {
    "meta": {
        "name": "Domingo Berbel",
        "headline": "Data Scientist",
        "location": "Madrid, Spain",
        "emails": ["info@domingoberbel.com"],
        "linkedin": "https://www.linkedin.com/in/domingo-berbel",
        "github": "https://github.com/dominberbel98",
    },
    "roles": [
        {
            "id": "data-equity",
            "company": "Data Equity",
            "title": "Data Scientist",
            "location": "Madrid, Spain",
            "start": "2025-10",
            "end": None,
            "summary": "Builds production data science for international clients.",
            "achievements": ["Shipped Power BI dashboards for pharma clients."],
            "stack": ["Python", "Power BI"],
        }
    ],
    "education": [
        {
            "id": "master-ucm",
            "institution": "Universidad Complutense de Madrid",
            "degree": "Master in Data Science, Big Data & Business Analytics",
            "start": "2024",
            "end": "2025",
            "grades": [{"subject": "Advanced Python", "score": 10.0}],
            "honours": ["Top grade in the final project"],
            "notes": "Focused on applied machine learning.",
        }
    ],
    "projects": [
        {
            "id": "portfolio-chatbot",
            "name": "Portfolio RAG chatbot",
            "year": 2026,
            "summary": "This site's conversational assistant.",
            "problem": "A static CV cannot answer what a given reader wants to know.",
            "approach": "Retrieval over a structured profile, with an agentic loop.",
            "stack": ["Python", "Power BI"],
            "outcome": "Deployed and serving live traffic.",
            "repo": "https://github.com/dominberbel98/agentic-rag-portfolio",
            "live_url": "https://domingoberbel.com",
        }
    ],
    "certifications": [
        {
            "id": "snowflake-snowpro",
            "title": "SnowPro Associate: Platform",
            "issuer": "Snowflake",
            "date": "2025-10",
            "expires": "2027-10",
            "image": "/certs/snowflake-snowpro.png",
            "skills": ["Snowflake"],
        }
    ],
    "skills": {
        "programming": ["Python"],
        "data": [],
        "cloud": [],
        "ml": [],
        "bi": ["Power BI"],
    },
    "languages": [
        {"language": "Spanish", "level": "Native"},
        {"language": "English", "level": "Professional", "evidence": "Erasmus in Slovakia."},
    ],
    "narrative": {
        "adaptability": "Has lived and worked independently since eighteen.",
        "resilience": "Changed career into data science deliberately.",
        "teamwork": "Co-built the master's final project with other engineers.",
        "career_change": "Moved from sales and marketing into data science.",
    },
}


@pytest.fixture
def minimal_profile() -> dict:
    """A schema-valid profile, deep-copied so tests can mutate it freely."""
    return copy.deepcopy(_MINIMAL)
