"""Farol-shaped knowledge seams with persistent and test-only adapters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol

from .storage import StateStore


class KnowledgeBackend(Protocol):
    def search(self, business_id: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]: ...

    def metadata(self) -> Dict[str, Any]: ...


class PersistentFarolKnowledge:
    """Durable local evidence backend used by the product runtime.

    It follows the useful Farol contract: approved sources are scoped by
    business, carry a version and locator, and revocation is checked at query
    time. It is deliberately not called the upstream optional RAG backend.
    """

    def __init__(self, store: StateStore):
        self.store = store

    def ingest(
        self,
        business_id: str,
        source_id: str,
        source_version: str,
        content: str,
        *,
        title: str = "",
        locator: str = "",
        origin: str = "local-approved",
        status: str = "approved",
        backend: str = "sqlite-farol-v1",
    ) -> Dict[str, Any]:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        source = {
            "business_id": business_id,
            "source_id": source_id,
            "source_version": source_version,
            "title": title or source_id,
            "content": content,
            "locator": locator or source_id,
            "origin": origin,
            "status": status,
            "content_hash": digest,
            "backend": backend,
        }
        self.store.put_source(source)
        return source

    def ingest_package_sources(self, business_id: str, package: Mapping[str, Any]) -> int:
        count = 0
        for source in package.get("sources", []):
            self.ingest(
                business_id,
                str(source["id"]),
                str(source["version"]),
                str(source["content"]),
                title=str(source.get("title", source["id"])),
                locator=str(source.get("locator", source["id"])),
                origin=str(source.get("origin", "package")),
                status=str(source.get("status", "approved")),
                backend="sqlite-farol-v1",
            )
            count += 1
        return count

    def search(self, business_id: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        return self.store.search_sources(business_id, query, max_results)

    def revoke(self, business_id: str, source_id: str, source_version: Optional[str] = None) -> int:
        return self.store.revoke_source(business_id, source_id, source_version)

    def metadata(self) -> Dict[str, Any]:
        return {
            "backend": "sqlite-farol-v1",
            "mode": "persistent-local",
            "production_claim": False,
            "supports": ["business-isolation", "origin", "version", "revocation"],
        }


class FarolArtifactImporter:
    """Import a generated Farol artifact without pretending it is in-memory RAG."""

    def __init__(self, backend: PersistentFarolKnowledge):
        self.backend = backend

    def import_package(self, business_id: str, package_root: Path | str) -> int:
        root = Path(package_root).expanduser().resolve()
        documents_root = root / "rag" / "documents"
        if not documents_root.is_dir():
            raise FileNotFoundError("artefato Farol sem rag/documents: %s" % root)
        metadata_by_path: Dict[str, Dict[str, Any]] = {}
        metadata_path = root / "rag" / "sources.json"
        if metadata_path.is_file():
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            for item in payload.get("sources", []):
                if isinstance(item, Mapping) and item.get("destination"):
                    metadata_by_path[str(item["destination"]).lstrip("./")] = dict(item)
        count = 0
        for path in sorted(documents_root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if count >= 1000:
                raise ValueError("artefato Farol excede 1000 documentos")
            if path.stat().st_size > 5_000_000:
                raise ValueError("documento Farol excede 5 MB: %s" % path.name)
            relative = path.relative_to(documents_root).as_posix()
            metadata = metadata_by_path.get(relative, {})
            self.backend.ingest(
                business_id,
                str(metadata.get("source_id", relative)),
                str(metadata.get("observed_revision", "farol-artifact")),
                path.read_text(encoding="utf-8", errors="replace"),
                title=str(metadata.get("title", relative)),
                locator=relative,
                origin="farol-artifact",
                status="approved",
                backend="farol-artifact-v1",
            )
            count += 1
        return count


class InMemoryKnowledge:
    """Test-only adapter; reports its non-production mode explicitly."""

    def __init__(self, documents: Mapping[str, str]):
        self.documents = dict(documents)

    def search(self, business_id: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        query_tokens = {token.casefold() for token in query.split() if token.strip()}
        hits = []
        for source_id, content in self.documents.items():
            score = sum(1 for token in query_tokens if token in content.casefold())
            if score:
                hits.append(
                    {
                        "evidence_id": "memory:%s:%s" % (business_id, source_id),
                        "business_id": business_id,
                        "source_id": source_id,
                        "source_version": "memory",
                        "content": content,
                        "locator": source_id,
                        "score": float(score),
                        "backend": "memory-test-only",
                    }
                )
        return sorted(hits, key=lambda item: -item["score"])[:max_results]

    def metadata(self) -> Dict[str, Any]:
        return {"backend": "memory-test-only", "mode": "test-only", "production_claim": False}
