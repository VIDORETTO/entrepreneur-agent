"""Install agent instructions and skills into a user's project.

The workspace is the directory where a person runs Claude Code, Codex or a
similar agent.  Installation never overwrites user-authored content: managed
text lives between markers and every other file is tracked by SHA-256 in a
small registry, so an edited file is kept unless the caller forces it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import __version__
from .skills import SkillCatalog

REGISTRY_NAME = ".vendedor-workspace.json"
TARGETS = ("claude", "codex", "all")
SKILL_ROOTS = {"claude": ".claude", "codex": ".agents"}
BLOCK_PATTERN = re.compile(r"<!-- vendedor-adaptavel:begin[^>]*-->.*?<!-- vendedor-adaptavel:end -->", re.DOTALL)
BEGIN_MARKER = "<!-- vendedor-adaptavel:begin v%s -->"
END_MARKER = "<!-- vendedor-adaptavel:end -->"
AGENTS_HEADER = "# AGENTS.md\n\n"
AGENTS_FOOTER = (
    "\n\n## Notas deste projeto\n\n"
    "Escreva aqui o que é específico do seu negócio (tom, regras internas, contatos). "
    "O bloco acima é atualizado por `vendedor skills install`; este texto nunca é alterado.\n"
)
CLAUDE_BLOCK = (
    "@AGENTS.md\n\n"
    "As regras acima valem para o Claude Code. As skills `seller-*` e `sales-*` estão em `.claude/skills/`.\n"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _template() -> str:
    repository = Path(__file__).resolve().parent / "resources" / "workspace" / "AGENTS.md"
    if repository.is_file():
        return repository.read_text(encoding="utf-8")
    return resources.files("sales_agent").joinpath("resources/workspace/AGENTS.md").read_text(encoding="utf-8")


def _managed_block(body: str) -> str:
    return "%s\n%s\n%s" % (BEGIN_MARKER % __version__, body.strip("\n"), END_MARKER)


class AgentWorkspace:
    def __init__(self, root: Path, catalog: Optional[SkillCatalog] = None):
        self.root = Path(root).expanduser().resolve()
        self.catalog = catalog or SkillCatalog(include_adaptation=True)

    # -- registry ---------------------------------------------------------
    def _load_registry(self) -> Dict[str, Any]:
        path = self.root / REGISTRY_NAME
        if not path.is_file():
            return {"schema": 1, "package_version": __version__, "files": {}}
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return {"schema": 1, "package_version": __version__, "files": {}}
        registry.setdefault("files", {})
        return registry

    # -- desired state ----------------------------------------------------
    def _skill_files(self, target: str) -> Dict[str, bytes]:
        base = SKILL_ROOTS[target]
        files: Dict[str, bytes] = {}
        for skill in self.catalog.list_skills():
            skill_dir = Path(skill["path"]).parent
            for source in sorted(skill_dir.rglob("*")):
                if source.is_file() and "__pycache__" not in source.parts:
                    relative = "%s/skills/%s/%s" % (base, skill["id"], source.relative_to(skill_dir).as_posix())
                    files[relative] = source.read_bytes()
            for reference in skill["references"]:
                if not reference["available"]:
                    continue
                destination = os.path.normpath("%s/skills/%s/%s" % (base, skill["id"], reference["reference"]))
                if not destination.startswith(base + "/"):
                    continue
                files.setdefault(Path(destination).as_posix(), Path(reference["path"]).read_bytes())
        return files

    # -- operations -------------------------------------------------------
    def install(self, target: str = "all", *, force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        if target not in TARGETS:
            raise ValueError("alvo desconhecido: %s" % target)
        targets = ("claude", "codex") if target == "all" else (target,)
        registry = self._load_registry()
        files: Dict[str, Any] = registry["files"]
        report: Dict[str, Any] = {
            "directory": str(self.root),
            "targets": list(targets),
            "dry_run": dry_run,
            "written": [],
            "unchanged": [],
            "skipped": [],
        }

        blocks: List[Tuple[str, str, str, str]] = [
            ("AGENTS.md", _managed_block(_template()), AGENTS_HEADER, AGENTS_FOOTER)
        ]
        if "claude" in targets:
            blocks.append(("CLAUDE.md", _managed_block(CLAUDE_BLOCK), "# CLAUDE.md\n\n", "\n"))
        for relative, block, header, footer in blocks:
            self._apply_block(relative, block, header, footer, files, report, force, dry_run)

        for selected in targets:
            for relative, content in self._skill_files(selected).items():
                self._apply_file(relative, content, files, report, force, dry_run)

        registry.update({"schema": 1, "package_version": __version__, "files": dict(sorted(files.items()))})
        if not dry_run:
            self.root.mkdir(parents=True, exist_ok=True)
            self._write_text(self.root / REGISTRY_NAME, json.dumps(registry, indent=2, sort_keys=True) + "\n")
        for key in ("written", "unchanged"):
            report[key].sort()
        return report

    def _write_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)

    def _write_text(self, path: Path, text: str) -> None:
        current = path.read_bytes() if path.is_file() else None
        data = text.encode("utf-8")
        if current != data:
            self._write_bytes(path, data)

    def _decide(
        self, relative: str, current_hash: Optional[str], new_hash: str, files: Mapping[str, Any], force: bool
    ) -> Tuple[str, str]:
        """Return (action, reason) where action is write, unchanged or skip."""

        if current_hash is None:
            return "write", ""
        if current_hash == new_hash:
            return "unchanged", ""
        recorded = files.get(relative, {}).get("sha256")
        if force or recorded == current_hash:
            return "write", ""
        return "skip", "modified" if recorded else "unregistered_conflict"

    def _apply_file(
        self,
        relative: str,
        content: bytes,
        files: Dict[str, Any],
        report: Dict[str, Any],
        force: bool,
        dry_run: bool,
    ) -> None:
        path = self.root / relative
        if path.is_symlink():
            report["skipped"].append({"path": relative, "reason": "symlink"})
            return
        current = path.read_bytes() if path.is_file() else None
        new_hash = _sha256(content)
        action, reason = self._decide(relative, _sha256(current) if current is not None else None, new_hash, files, force)
        if action == "skip":
            report["skipped"].append({"path": relative, "reason": reason})
            return
        if action == "write":
            if not dry_run:
                self._write_bytes(path, content)
            report["written"].append(relative)
        else:
            report["unchanged"].append(relative)
        files[relative] = {"sha256": new_hash, "version": __version__}

    def _apply_block(
        self,
        relative: str,
        block: str,
        header: str,
        footer: str,
        files: Dict[str, Any],
        report: Dict[str, Any],
        force: bool,
        dry_run: bool,
    ) -> None:
        path = self.root / relative
        if path.is_symlink():
            report["skipped"].append({"path": relative, "reason": "symlink"})
            return
        new_hash = _sha256(block.encode("utf-8"))
        if not path.is_file():
            updated = header + block + footer
            current_hash = None
        else:
            text = path.read_text(encoding="utf-8")
            match = BLOCK_PATTERN.search(text)
            if match:
                current_hash = _sha256(match.group(0).encode("utf-8"))
                updated = text[: match.start()] + block + text[match.end():]
            else:
                current_hash = None
                separator = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
                updated = text + separator + block + "\n"
        action, reason = self._decide(relative, current_hash, new_hash, files, force)
        if action == "skip":
            report["skipped"].append({"path": relative, "reason": reason})
            return
        if action == "write":
            if not dry_run:
                self._write_text(path, updated)
            report["written"].append(relative)
        else:
            report["unchanged"].append(relative)
        files[relative] = {"sha256": new_hash, "version": __version__, "managed_block": True}

    def status(self) -> Dict[str, Any]:
        registry_path = self.root / REGISTRY_NAME
        if not registry_path.is_file():
            return {"directory": str(self.root), "installed": False, "ok": False, "outdated": False, "files": []}
        registry = self._load_registry()
        desired: Dict[str, str] = {}
        block_sources = {"AGENTS.md": _managed_block(_template()), "CLAUDE.md": _managed_block(CLAUDE_BLOCK)}
        for relative, block in block_sources.items():
            desired[relative] = _sha256(block.encode("utf-8"))
        for target in SKILL_ROOTS:
            desired.update({rel: _sha256(data) for rel, data in self._skill_files(target).items()})

        entries: List[Dict[str, Any]] = []
        update_available = False
        for relative, record in sorted(registry["files"].items()):
            path = self.root / relative
            if not path.is_file():
                state = "missing"
            else:
                if record.get("managed_block"):
                    match = BLOCK_PATTERN.search(path.read_text(encoding="utf-8"))
                    current = _sha256(match.group(0).encode("utf-8")) if match else None
                else:
                    current = _sha256(path.read_bytes())
                state = "ok" if current == record.get("sha256") else "modified"
            entries.append({"path": relative, "state": state})
            if desired.get(relative) not in (None, record.get("sha256")):
                update_available = True
        outdated = registry.get("package_version") != __version__ or update_available
        return {
            "directory": str(self.root),
            "installed": True,
            "package_version": registry.get("package_version"),
            "current_version": __version__,
            "outdated": outdated,
            "ok": not outdated and all(item["state"] == "ok" for item in entries),
            "files": entries,
        }


def install_agent_files(directory: Path, target: str, *, force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    return AgentWorkspace(directory).install(target, force=force, dry_run=dry_run)


__all__: Sequence[str] = ("AgentWorkspace", "TARGETS", "install_agent_files")
