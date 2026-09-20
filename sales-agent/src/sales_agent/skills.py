"""Installed skill catalog and runtime selection.

Skills provide interpretation guidance. They never grant a capability or write
to a connector; those decisions remain in the package and the runtime.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

SKILL_VERSION = "1"
DEFAULT_CONTEXT_BUDGET = 8_000
MAX_CONTEXT_BUDGET = 64_000
AUDIENCES = {
    "sales-setup": "business-configuration",
    "sales-business-discovery": "business-configuration",
    "sales-knowledge-preparation": "business-configuration",
    "sales-simulate": "business-configuration",
    "seller-conversation": "buyer-attention",
}


class SkillCatalog:
    """Discover skills from the checkout or the installed data directory."""

    def __init__(self, roots: Optional[List[Union[Path, str]]] = None):
        repository_root = Path(__file__).resolve().parents[2]
        default_roots = [
            repository_root / "skills",
            Path(sys.prefix) / "share" / "vendedor-adaptavel" / "skills",
        ]
        self.roots = [Path(root).expanduser().resolve() for root in (roots or default_roots)]

    def _skill_paths(self) -> Dict[str, Path]:
        found: Dict[str, Path] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for skill_file in sorted(root.glob("*/SKILL.md")):
                found.setdefault(skill_file.parent.name, skill_file)
        return found

    @staticmethod
    def _frontmatter(content: str) -> Dict[str, str]:
        if not content.startswith("---"):
            return {}
        lines = content.splitlines()
        try:
            end = lines.index("---", 1)
        except ValueError:
            return {}
        values: Dict[str, str] = {}
        for line in lines[1:end]:
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip()] = value.strip().strip('"')
        return values

    @staticmethod
    def _context_budget(package: Mapping[str, Any]) -> int:
        settings = package.get("settings", {})
        value = settings.get("skill_context_budget", DEFAULT_CONTEXT_BUDGET) if isinstance(settings, Mapping) else 0
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > MAX_CONTEXT_BUDGET:
            return 0
        return value

    @staticmethod
    def _references(skill_dir: Path, content: str) -> List[str]:
        references = re.findall(r"`([^`\n]+)`", content) + re.findall(r"\]\(([^)]+)\)", content)
        return [item.strip() for item in references if item.strip().endswith((".md", ".json", ".py"))]

    def list_skills(self) -> List[Dict[str, Any]]:
        result = []
        for skill_id, path in self._skill_paths().items():
            content = path.read_text(encoding="utf-8")
            metadata = self._frontmatter(content)
            audience = AUDIENCES.get(skill_id)
            if audience is None:
                continue
            refs = self._resolved_references(path, content)
            result.append(
                {
                    "id": skill_id,
                    "name": metadata.get("name", skill_id),
                    "description": metadata.get("description", ""),
                    "version": metadata.get("version", SKILL_VERSION),
                    "audience": audience,
                    "path": str(path),
                    "available": all(item["available"] for item in refs),
                    "references": refs,
                }
            )
        return sorted(result, key=lambda item: item["id"])

    def _resolved_references(self, path: Path, content: str) -> List[Dict[str, Any]]:
        result = []
        package_root = path.parent.parent.parent.resolve()
        for reference in self._references(path.parent, content):
            candidate = (path.parent / reference).resolve()
            if not candidate.is_file():
                # Installed skills keep their references beside the package's
                # share directory, while the markdown retains repository paths.
                candidate = (path.parent.parent.parent / reference.removeprefix("../../")).resolve()
            try:
                candidate.relative_to(package_root)
                inside_package = True
            except ValueError:
                inside_package = False
            available = inside_package and candidate.is_file()
            item: Dict[str, Any] = {"reference": reference, "path": str(candidate), "available": available}
            if available and candidate.stat().st_size <= 1_000_000:
                item["content"] = candidate.read_text(encoding="utf-8")
            result.append(item)
        return result

    def read_skill(self, skill_id: str) -> Dict[str, Any]:
        path = self._skill_paths().get(skill_id)
        if not path:
            return {"id": skill_id, "available": False, "reason": "skill desconhecida", "references": []}
        content = path.read_text(encoding="utf-8")
        metadata = self._frontmatter(content)
        references = self._resolved_references(path, content)
        return {
            "id": skill_id,
            "name": metadata.get("name", skill_id),
            "description": metadata.get("description", ""),
            "version": metadata.get("version", SKILL_VERSION),
            "audience": AUDIENCES.get(skill_id),
            "content": content,
            "references": references,
            "available": all(item["available"] for item in references),
        }

    def diagnose(self) -> Dict[str, Any]:
        skills = self.list_skills()
        return {
            "ok": bool(skills) and all(item["available"] for item in skills),
            "roots": [str(root) for root in self.roots],
            "skills": [
                {
                    "id": item["id"],
                    "version": item["version"],
                    "audience": item["audience"],
                    "available": item["available"],
                    "references": item["references"],
                }
                for item in skills
            ],
        }

    def select(self, package: Mapping[str, Any], text: str, state: Mapping[str, Any]) -> Dict[str, Any]:
        declared = [item for item in package.get("skills", []) if isinstance(item, Mapping)]
        catalog = {item["id"]: item for item in self.list_skills()}
        available = []
        selected = []
        unavailable = []
        applied = []
        budget = self._context_budget(package)
        remaining = budget
        for item in declared:
            skill_id = str(item.get("id", ""))
            record = catalog.get(skill_id)
            if not record or record["audience"] != "buyer-attention":
                if skill_id and not record:
                    unavailable.append({"id": skill_id, "reason": "unknown_skill"})
                continue
            declared_version = str(item.get("version", record["version"]))
            if record["available"] and declared_version == record["version"]:
                available.append({"id": skill_id, "version": record["version"], "audience": record["audience"]})
            if declared_version != record["version"]:
                unavailable.append({"id": skill_id, "reason": "version_mismatch"})
                continue
            trigger = str(item.get("when", "always"))
            value = text.casefold()
            eligible = trigger == "always" or (trigger in {"objection", "objection-or-material"} and any(word in value for word in ("mas", "porém", "garantia", "caro"))) or (trigger in {"material", "objection-or-material"} and bool(state.get("pending")))
            if not eligible:
                continue
            if not record["available"]:
                unavailable.append({"id": skill_id, "reason": "resource_unavailable"})
                continue
            selected_item = {"id": skill_id, "version": record["version"], "audience": record["audience"]}
            selected.append(selected_item)
            if remaining <= 0:
                unavailable.append({"id": skill_id, "reason": "context_budget"})
                continue
            requested = item.get("context_chars", remaining)
            if isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0:
                requested = remaining
            content = str(self.read_skill(skill_id).get("content", ""))
            applied_chars = min(len(content), requested, remaining)
            if applied_chars <= 0:
                unavailable.append({"id": skill_id, "reason": "context_budget"})
                continue
            applied_item = {**selected_item, "context_chars": applied_chars}
            selected_item["context_chars"] = applied_chars
            remaining -= applied_chars
            # ``applied`` is the exact, bounded context sent to the model; the
            # trace contains only identity and size, never the skill text.
            applied.append(applied_item)
        return {
            "declared": [str(item.get("id", "")) for item in declared],
            "available": available,
            "selected": selected,
            "unavailable": unavailable,
            # ``context_prepared`` is the honest local fact.  ``applied`` is
            # retained as a compatibility alias for existing diagnostics.
            "context_prepared": applied,
            "applied": applied,
            "sent_to_model": [dict(item) for item in applied],
            "budget": {"limit": budget, "used": budget - remaining},
        }

    def context(self, selected: Mapping[str, Any], *, max_chars: int = 8_000) -> List[Dict[str, str]]:
        context = []
        for item in selected.get("applied", []):
            record = self.read_skill(str(item["id"]))
            limit = min(max_chars, int(item.get("context_chars", max_chars)))
            context.append({"id": str(item["id"]), "version": str(item["version"]), "content": record.get("content", "")[:limit]})
        return context
