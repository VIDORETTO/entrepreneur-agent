"""Farol-shaped knowledge seams with persistent and test-only adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple, Union

from .storage import StateStore, normalize_iso_datetime, utc_now


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class KnowledgeBackend(Protocol):
    def search(
        self,
        business_id: str,
        query: str,
        max_results: int = 5,
        *,
        audience: str = "",
        scope: str = "",
        subject: str = "",
    ) -> List[Dict[str, Any]]: ...

    def metadata(self) -> Dict[str, Any]: ...


class StableFarolAdapter:
    """Status/reporting seam for the not-yet-published Farol stable contract.

    The product can query local imported generations today.  This adapter never
    silently falls back to that backend when a caller requests the external
    stable service; it returns a structured blocked/incompatible result until a
    compatible client is explicitly supplied.
    """

    # No stable public contract was verified in this environment.  Keeping a
    # placeholder label here would make a blocked status look like a fixed
    # compatibility claim.
    supported_contract: Optional[str] = None

    def __init__(self, client: Any = None, *, expected_revision: Optional[str] = None):
        self.client = client
        self.expected_revision = expected_revision

    def status(self) -> Dict[str, Any]:
        if self.client is None:
            return {
                "status": "blocked",
                "reason": "versão estável e cliente executável do Farol não disponíveis",
                "contract": None,
                "contract_status": "unresolved",
                "expected_revision": self.expected_revision,
                "production_claim": False,
            }
        revision = getattr(self.client, "revision", None)
        contract = getattr(self.client, "contract", None)
        if self.supported_contract is None or contract != self.supported_contract or (self.expected_revision and revision != self.expected_revision):
            return {
                "status": "incompatible",
                "reason": "cliente não corresponde ao contrato/revisão fixados",
                "contract": contract,
                "contract_status": "unresolved",
                "revision": revision,
                "expected_revision": self.expected_revision,
                "production_claim": False,
            }
        return {
            "status": "ready",
            "contract": contract,
            "contract_status": "verified",
            "revision": revision,
            "production_claim": False,
        }

    def query(self, business_id: str, query: str, *, audience: str = "", scope: str = "") -> Dict[str, Any]:
        state = self.status()
        if state["status"] != "ready":
            return {**state, "business_id": business_id, "query": query, "audience": audience, "scope": scope, "hits": []}
        try:
            value = self.client.query(business_id, query, audience=audience, scope=scope)
        except TimeoutError:
            return {**state, "status": "timeout", "business_id": business_id, "hits": []}
        except Exception as exc:
            return {**state, "status": "unavailable", "reason": str(exc)[:300], "business_id": business_id, "hits": []}
        if not isinstance(value, list):
            return {**state, "status": "incompatible", "reason": "resposta de consulta inválida", "business_id": business_id, "hits": []}
        return {**state, "status": "ok", "business_id": business_id, "hits": value}


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
        scope: str = "",
        audience: str = "",
        subject: str = "",
        valid_from: Optional[str] = None,
        valid_until: Optional[str] = None,
        active: Optional[bool] = None,
        generation: Optional[str] = None,
    ) -> Dict[str, Any]:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if active is None:
            existing = self.store.list_sources(business_id)
            same_revision = next(
                (
                    item
                    for item in existing
                    if item.get("source_id") == source_id and item.get("source_version") == source_version
                ),
                None,
            )
            if same_revision is not None:
                active = bool(same_revision.get("active"))
            else:
                active = not any(
                    item.get("active")
                    and item.get("status") == "approved"
                    and item.get("source_id") == source_id
                    and item.get("scope", "") == scope
                and item.get("audience", "") == audience
                and item.get("subject", "") == subject
                for item in existing
                )
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
            "scope": scope,
            "audience": audience,
            "subject": subject,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "active": bool(active),
            "generation": generation,
        }
        self.store.put_source(source)
        return source

    def ingest_package_sources(
        self,
        business_id: str,
        package: Mapping[str, Any],
        *,
        previous_package: Optional[Mapping[str, Any]] = None,
    ) -> int:
        """Install a package source snapshot while retaining immutable history."""

        existing = self.store.list_sources(business_id)
        effective = list(existing)
        staged: List[Dict[str, Any]] = []
        package_keys = set()
        for source in package.get("sources", []):
            source_id = str(source["id"])
            source_version = str(source["version"])
            scope = str(source.get("scope", ""))
            audience = str(source.get("audience", ""))
            subject = str(source.get("subject", ""))
            key = (source_id, source_version)
            package_keys.add(key)
            same_revision = next(
                (
                    item
                    for item in effective
                    if item.get("source_id") == source_id and item.get("source_version") == source_version
                ),
                None,
            )
            if "active" in source:
                active = bool(source["active"])
            elif same_revision is not None:
                active = bool(same_revision.get("active"))
            else:
                active = not any(
                    item.get("active")
                    and item.get("status") == "approved"
                    and item.get("source_id") == source_id
                    and item.get("scope", "") == scope
                    and item.get("audience", "") == audience
                    and item.get("subject", "") == subject
                    for item in effective
                )
            content = str(source["content"])
            value = {
                "business_id": business_id,
                "source_id": source_id,
                "source_version": source_version,
                "title": str(source.get("title", source_id)),
                "content": content,
                "locator": str(source.get("locator", source_id)),
                "origin": str(source.get("origin", "package")),
                "status": str(source.get("status", "approved")),
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "backend": "sqlite-farol-v1",
                "scope": scope,
                "audience": audience,
                "subject": subject,
                "valid_from": source.get("valid_from"),
                "valid_until": source.get("valid_until"),
                "active": active,
                "generation": source.get("generation"),
            }
            staged.append(value)
            effective.append({**value, "source_id": source_id, "source_version": source_version})

        previous_keys = {
            (str(source.get("id")), str(source.get("version")))
            for source in (previous_package or {}).get("sources", [])
            if isinstance(source, Mapping) and source.get("id") and source.get("version")
        }
        deactivate_keys = [
            {"business_id": business_id, "source_id": source_id, "source_version": source_version}
            for source_id, source_version in sorted(previous_keys - package_keys)
        ]
        self.store.put_sources_atomic(staged, deactivate_keys=deactivate_keys)
        return len(staged)

    def search(
        self,
        business_id: str,
        query: str,
        max_results: int = 5,
        *,
        as_of: Optional[str] = None,
        audience: str = "",
        scope: str = "",
        subject: str = "",
    ) -> List[Dict[str, Any]]:
        return self.store.search_sources(
            business_id, query, max_results, as_of=as_of, audience=audience, scope=scope, subject=subject
        )

    def revoke(self, business_id: str, source_id: str, source_version: Optional[str] = None) -> int:
        return self.store.revoke_source(business_id, source_id, source_version)

    def reapprove(self, business_id: str, source_id: str, source_version: Optional[str], reason: str) -> bool:
        """Explicitly reverse an owner revocation within its exact scope."""

        return bool(self.store.reapprove_source(business_id, source_id, source_version, reason))

    def evidence_is_current(
        self,
        business_id: str,
        source_id: str,
        source_version: str,
        evidence_id: str = "",
        expected_metadata: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Check the exact revision and its authorized context at delivery time."""

        with self.store.connect() as db:
            row = db.execute(
                "SELECT status, review_status, active, valid_from, valid_until, scope, audience, subject, generation "
                "FROM knowledge_sources WHERE business_id = ? AND source_id = ? AND source_version = ?",
                (business_id, source_id, source_version),
            ).fetchone()
        if not row or row["status"] != "approved" or row["review_status"] != "approved" or not row["active"]:
            return False
        expected_id = "%s:%s:%s" % (business_id, source_id, source_version)
        if evidence_id and evidence_id != expected_id:
            return False
        for field in ("scope", "audience", "subject", "generation"):
            if expected_metadata is not None and field in expected_metadata:
                if str(row[field] or "") != str(expected_metadata.get(field) or ""):
                    return False
        now = datetime.fromisoformat(self.store.clock.now().replace("Z", "+00:00"))
        try:
            valid_from = _parse_iso(row["valid_from"]) if row["valid_from"] else None
            valid_until = _parse_iso(row["valid_until"]) if row["valid_until"] else None
        except ValueError:
            return False
        return bool((not valid_from or valid_from <= now) and (not valid_until or valid_until > now))

    def promote(self, business_id: str, source_id: str, source_version: str) -> bool:
        """Make a revision current for its scope without deleting history."""

        with self.store._lock, self.store.connect() as db:  # public operation, transaction boundary only
            row = db.execute(
                "SELECT status, review_status, scope, audience, subject FROM knowledge_sources "
                "WHERE business_id = ? AND source_id = ? AND source_version = ?",
                (business_id, source_id, source_version),
            ).fetchone()
            if not row or row["status"] != "approved" or row["review_status"] != "approved":
                return False
            db.execute(
                "UPDATE knowledge_sources SET active = 0, updated_at = ? WHERE business_id = ? "
                "AND source_id = ? AND scope = ? AND audience = ? AND subject = ?",
                (utc_now(), business_id, source_id, row["scope"], row["audience"], row["subject"]),
            )
            cursor = db.execute(
                "UPDATE knowledge_sources SET active = 1, updated_at = ? WHERE business_id = ? AND source_id = ? AND source_version = ?",
                (utc_now(), business_id, source_id, source_version),
            )
            return cursor.rowcount == 1

    def metadata(self) -> Dict[str, Any]:
        return {
            "backend": "sqlite-farol-v1",
            "mode": "persistent-local",
            "production_claim": False,
            "supports": ["business-isolation", "origin", "version", "generation", "scope", "audience", "validity", "revocation"],
        }

    def list_sources(self, business_id: str) -> List[Dict[str, Any]]:
        return self.store.list_sources(business_id)

    def pending_reviews(self, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.store.list_pending_source_reviews(business_id)

    def review_legacy(self, business_id: str, source_id: str, source_version: str, reason: str) -> bool:
        return self.store.review_source(business_id, source_id, source_version, reason)


class FarolArtifactImporter:
    """Import a generated Farol artifact without pretending it is in-memory RAG."""

    def __init__(self, backend: PersistentFarolKnowledge):
        self.backend = backend
        self.last_report: Dict[str, Any] = {}

    def import_package(self, business_id: str, package_root: Union[Path, str]) -> int:
        requested_root = Path(package_root).expanduser()
        if requested_root.is_symlink():
            raise ValueError("artefato Farol não pode ter raiz symlink")
        root = requested_root.resolve()
        if not root.is_dir():
            raise FileNotFoundError("raiz do artefato Farol não é um diretório: %s" % root)
        rag_root = root / "rag"
        if rag_root.is_symlink():
            raise ValueError("artefato Farol não pode apontar rag para fora")
        if not rag_root.is_dir():
            raise FileNotFoundError("artefato Farol sem diretório rag: %s" % root)
        try:
            rag_root.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("artefato Farol tem diretório rag fora da raiz") from exc
        documents_root = rag_root / "documents"
        if not documents_root.is_dir():
            raise FileNotFoundError("artefato Farol sem rag/documents: %s" % root)
        if documents_root.is_symlink():
            raise ValueError("artefato Farol não pode apontar rag/documents para fora")
        try:
            documents_root.resolve().relative_to(rag_root.resolve())
        except ValueError as exc:
            raise ValueError("artefato Farol tem documentos fora de rag") from exc
        metadata_by_path: Dict[str, Dict[str, Any]] = {}
        upstream_revocations: set[tuple[str, Optional[str]]] = set()
        upstream_revoked_ids: set[str] = set()
        metadata_path = rag_root / "sources.json"
        if metadata_path.is_symlink():
            raise ValueError("manifesto Farol não pode ser symlink")
        legacy = not metadata_path.is_file()
        if legacy:
            # Older local fixtures only exposed ``rag/documents``. Keep that
            # migration usable, but make the generated revision and warning
            # explicit so it cannot be mistaken for proof of the stable Farol
            # contract. New artifacts still require their signed metadata.
            payload = {"schema_version": 0, "generation": "legacy-migration", "sources": []}
            self.last_report = {
                "mode": "legacy-migration",
                "production_claim": False,
                "warning": "manifesto rag/sources.json ausente; revisões derivadas do hash do documento",
            }
        else:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                not isinstance(payload, Mapping)
                or payload.get("schema_version") != 1
                or not isinstance(payload.get("generation"), str)
                or not payload.get("generation").strip()
            ):
                raise ValueError("artefato Farol incompatível: geração ou schema ausente")
            manifest_sources = payload.get("sources", [])
            manifest_revocations = payload.get("revocations", [])
            if not isinstance(manifest_sources, list) or not isinstance(manifest_revocations, list):
                raise ValueError("artefato Farol incompatível: sources/revocations precisam ser listas")
            for item in manifest_sources:
                if not isinstance(item, Mapping) or not item.get("destination"):
                    raise ValueError("manifesto Farol contém registro de documento incompleto")
                raw_key = str(item["destination"])
                key = raw_key
                while key.startswith("./"):
                    key = key[2:]
                if raw_key.startswith("/") or ".." in Path(raw_key).parts or "\\" in raw_key or not key:
                    raise ValueError("manifesto Farol contém caminho fora de rag/documents: %s" % raw_key)
                if not item.get("source_id"):
                    raise ValueError("manifesto Farol sem source_id para: %s" % raw_key)
                if key in metadata_by_path:
                    raise ValueError("manifesto Farol contém destino duplicado: %s" % key)
                metadata_by_path[key] = dict(item)
            for item in manifest_revocations:
                if not isinstance(item, Mapping) or not item.get("source_id"):
                    raise ValueError("manifesto Farol contém revogação incompleta")
                source_id = str(item["source_id"])
                version = item.get("source_version") or item.get("version")
                if version is None:
                    upstream_revoked_ids.add(source_id)
                else:
                    upstream_revocations.add((source_id, str(version)))
        staged = []
        seen_destinations = set()
        seen_revisions = set()
        active_revisions: Dict[Tuple[str, str, str, str], str] = {}
        count = 0
        total_bytes = 0
        for path in sorted(documents_root.rglob("*")):
            if path.is_symlink():
                raise ValueError("artefato Farol não pode conter symlink: %s" % path.name)
            if not path.is_file():
                continue
            if count >= 1000:
                raise ValueError("artefato Farol excede 1000 documentos")
            size = path.stat().st_size
            if size > 5_000_000:
                raise ValueError("documento Farol excede 5 MB: %s" % path.name)
            total_bytes += size
            if total_bytes > 50_000_000:
                raise ValueError("artefato Farol excede 50 MB")
            relative = path.relative_to(documents_root).as_posix()
            try:
                path.resolve().relative_to(documents_root.resolve())
            except ValueError as exc:
                raise ValueError("documento Farol aponta para fora da raiz") from exc
            seen_destinations.add(relative)
            content = path.read_text(encoding="utf-8", errors="replace")
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            metadata = metadata_by_path.get(relative)
            if legacy:
                metadata = {"source_id": relative, "title": relative, "active": False, "status": "pending_review"}
                revision = "legacy-sha256:%s" % digest
                expected_hash = digest
            else:
                if not metadata:
                    raise ValueError("artefato Farol sem metadados para revisão: %s" % relative)
                revision = metadata.get("observed_revision") or metadata.get("revision")
                if not isinstance(revision, str) or not revision.strip():
                    raise ValueError("artefato Farol sem revisão para: %s" % relative)
                expected_hash = metadata.get("sha256") or metadata.get("content_hash")
                if not isinstance(expected_hash, str) or not expected_hash.strip():
                    raise ValueError("artefato Farol sem hash de conteúdo para: %s" % relative)
            if expected_hash and expected_hash != digest:
                raise ValueError("hash divergente no documento Farol: %s" % relative)
            revision_key = (str(metadata.get("source_id", relative)), revision)
            if revision_key in seen_revisions:
                raise ValueError("artefato Farol contém revisão duplicada: %s@%s" % revision_key)
            seen_revisions.add(revision_key)
            source_id = str(metadata.get("source_id", relative))
            upstream_status = metadata.get("status") or "pending_review"
            if upstream_status not in {"approved", "revoked", "pending", "pending_review"}:
                raise ValueError("manifesto Farol tem status inválido: %s" % relative)
            revoked = bool(
                metadata.get("revoked")
                or upstream_status == "revoked"
                or (source_id, revision) in upstream_revocations
                or source_id in upstream_revoked_ids
            )
            status = "revoked" if revoked else ("pending" if upstream_status in {"pending", "pending_review"} else "approved")
            review_status = "pending_review" if legacy or status == "pending" else "approved"
            if not isinstance(metadata.get("active", True), bool):
                raise ValueError("manifesto Farol tem active inválido: %s" % relative)
            valid_from = metadata.get("valid_from")
            valid_until = metadata.get("valid_until")
            for field, value in (("valid_from", valid_from), ("valid_until", valid_until)):
                if value is not None:
                    if not isinstance(value, str):
                        raise ValueError("manifesto Farol tem %s inválido: %s" % (field, relative))
                    try:
                        normalized = normalize_iso_datetime(value)
                    except ValueError as exc:
                        raise ValueError("manifesto Farol tem %s inválido: %s" % (field, relative)) from exc
                    if field == "valid_from":
                        valid_from = normalized
                    else:
                        valid_until = normalized
            if valid_from and valid_until and normalize_iso_datetime(valid_from) >= normalize_iso_datetime(valid_until):
                raise ValueError("manifesto Farol tem vigência inválida: %s" % relative)
            staged.append(
                {
                    "business_id": business_id,
                    "source_id": source_id,
                    "source_version": revision,
                    "content": content,
                    "title": str(metadata.get("title", relative)),
                    "locator": relative,
                    "origin": "farol-artifact-legacy-migration" if legacy else "farol-artifact",
                    "status": status,
                    "backend": "farol-artifact-v1",
                    "content_hash": digest,
                    "scope": str(metadata.get("scope", "")),
                    "audience": str(metadata.get("audience", "")),
                    "subject": str(metadata.get("subject", "")),
                    "active": bool(metadata.get("active", True)) and status == "approved" and not legacy,
                    "generation": ("legacy:%s" % digest) if legacy else str(payload["generation"]),
                    "valid_from": valid_from,
                    "valid_until": valid_until,
                    "review_status": review_status,
                }
            )
            active_key = (source_id, str(metadata.get("scope", "")), str(metadata.get("audience", "")), str(metadata.get("subject", "")))
            if status == "approved" and bool(metadata.get("active", True)):
                previous_active = active_revisions.get(active_key)
                if previous_active is not None and previous_active != revision:
                    raise ValueError(
                        "artefato Farol contém mais de uma revisão ativa para o mesmo escopo: %s" % source_id
                    )
                active_revisions[active_key] = revision
            count += 1
        if not legacy:
            missing_files = sorted(set(metadata_by_path) - seen_destinations)
            if missing_files:
                raise ValueError("manifesto Farol referencia documento ausente: %s" % missing_files[0])
        if not staged:
            raise ValueError("artefato Farol não contém documentos")
        revocations = []
        if not legacy:
            revocations = [
                {
                    "business_id": business_id,
                    "source_id": item.get("source_id"),
                    "source_version": item.get("source_version") or item.get("version"),
                }
                for item in manifest_revocations
                if isinstance(item, Mapping) and item.get("source_id")
            ]
        self.backend.store.put_sources_atomic(
            staged, generation=None if legacy else str(payload["generation"]), revocations=revocations
        )
        if not self.last_report:
            self.last_report = {
                "mode": "manifest-v1",
                "generation": str(payload["generation"]),
                "production_claim": False,
            }
        self.last_report["documents"] = count
        return count


class InMemoryKnowledge:
    """Test-only adapter; reports its non-production mode explicitly."""

    def __init__(self, documents: Mapping[str, str]):
        self.documents = dict(documents)

    def search(
        self,
        business_id: str,
        query: str,
        max_results: int = 5,
        *,
        audience: str = "",
        scope: str = "",
        subject: str = "",
    ) -> List[Dict[str, Any]]:
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
