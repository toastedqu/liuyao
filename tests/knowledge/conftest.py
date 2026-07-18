"""Shared fixtures for ``app.knowledge`` tests.

The knowledge base is built once per test session (parsing + indexing all
141 chapters takes a few seconds) into a scratch directory *inside the
repository* (``tests/knowledge/.tmp_build/``), never under a system temp
directory, and removed again at the end of the session.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.knowledge.ingest import build_database
from app.knowledge.parser import parse_corpus
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.retrieval import Retriever

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "zengshan_buyi"
WORKDIR = Path(__file__).resolve().parent / ".tmp_build"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def source_dir() -> Path:
    return SOURCE_DIR


@pytest.fixture(scope="session")
def build_workdir():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    yield WORKDIR
    shutil.rmtree(WORKDIR, ignore_errors=True)


@pytest.fixture(scope="session")
def parsed_corpus():
    """Parse every chapter once, without touching SQLite."""

    return parse_corpus(SOURCE_DIR, repo_root=REPO_ROOT)


@pytest.fixture(scope="session")
def knowledge_db_path(build_workdir):
    db_path = build_workdir / "knowledge.sqlite3"
    build_database(SOURCE_DIR, db_path, repo_root=REPO_ROOT)
    return db_path


@pytest.fixture(scope="session")
def knowledge_repo(knowledge_db_path):
    with KnowledgeRepository.open(knowledge_db_path) as repo:
        yield repo


@pytest.fixture()
def retriever(knowledge_repo):
    return Retriever(knowledge_repo)
