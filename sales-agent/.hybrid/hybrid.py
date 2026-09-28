#!/usr/bin/env python3
"""Deterministic local runtime for the hybrid development skills.

The skills contain the semantic workflow.  This module deliberately handles
only facts that can be checked without a model: artifact shape, stable IDs,
references, dependency graphs, generated views, optimistic checkpoints,
fingerprints, evidence freshness, and finding deduplication.

It uses only the Python standard library so that an installed project does not
inherit a package manager requirement from the skills bundle.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


SCRIPT_PATH = Path(__file__).resolve()
if (SCRIPT_PATH.parent / "shared").is_dir():
    PACKAGE_ROOT = SCRIPT_PATH.parent
elif (SCRIPT_PATH.parent.parent / "shared").is_dir():
    PACKAGE_ROOT = SCRIPT_PATH.parent.parent
else:
    PACKAGE_ROOT = SCRIPT_PATH.parent
SHARED_ROOT = PACKAGE_ROOT / "shared"

CONFIG_REL = Path(".hybrid") / "config.json"
GENERATED_REL = Path(".hybrid") / "generated.json"

EFFORT_PHASES = [
    "discovery",
    "specification",
    "planning",
    "slicing",
    "implementation",
    "verification",
    "review",
    "convergence",
    "delivery",
    "closed",
]
EFFORT_STATUSES = {
    "active",
    "waiting_input",
    "blocked_external",
    "failed",
    "complete",
    "cancelled",
}
TICKET_STATUSES = {
    "draft",
    "ready",
    "in_progress",
    "implemented",
    "verified",
    "done",
    "blocked",
    "cancelled",
    "superseded",
}
EVIDENCE_RESULTS = {"passed", "failed", "partial", "not_run", "stale"}
VERIFICATION_STATUSES = {"not_run", "partial", "passed", "failed", "stale"}
ID_PATTERNS = {
    "TK": re.compile(r"^TK-(\d{3,})$"),
    "FR": re.compile(r"^FR-(\d{3,})$"),
    "AC": re.compile(r"^AC-(\d{3,})$"),
    "EV": re.compile(r"^EV-(\d{3,})$"),
    "FD": re.compile(r"^FD-(\d{3,})$"),
}


class HybridError(Exception):
    """An expected user or artifact error with a useful machine-readable code."""

    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def safe_project_path(project: Path, value: str | Path) -> Path:
    candidate = (project / Path(value)).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError as exc:
        raise HybridError(f"Path escapes project: {value}", "unsafe_path") from exc
    return candidate


def directory_fingerprint(path: Path, root: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return "missing:" + sha256_bytes(rel_path(path, root).encode("utf-8"))
    if path.is_file():
        return sha256_file(path)
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        relative = child.relative_to(path).as_posix()
        if any(part in {".git", ".hybrid", "__pycache__"} for part in child.parts):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(child).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def fingerprint_paths(project: Path, paths: Sequence[str]) -> tuple[str, dict[str, str]]:
    values: dict[str, str] = {}
    for raw in paths:
        normalized = Path(raw).as_posix()
        target = safe_project_path(project, normalized)
        values[normalized] = directory_fingerprint(target, project)
    digest = hashlib.sha256()
    for key in sorted(values):
        digest.update(key.encode("utf-8"))
        digest.update(b"=")
        digest.update(values[key].encode("ascii"))
        digest.update(b"\0")
    return "local:" + digest.hexdigest(), values


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HybridError(f"Missing JSON file: {path}", "missing_file") from exc
    except json.JSONDecodeError as exc:
        raise HybridError(f"Invalid JSON in {path}: {exc}", "invalid_json") from exc


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        parts: list[str] = []
        current: list[str] = []
        quote: str | None = None
        for char in inner:
            if char in {"'", '"'}:
                if quote == char:
                    quote = None
                elif quote is None:
                    quote = char
            if char == "," and quote is None:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        parts.append("".join(current).strip())
        return [parse_scalar(part) for part in parts if part]
    if value.startswith("{") and value.endswith("}"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise HybridError("Frontmatter starts with --- but has no closing ---", "frontmatter")
    metadata: dict[str, Any] = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if not match:
            raise HybridError(f"Invalid frontmatter line: {line}", "frontmatter")
        key, raw = match.groups()
        if raw in {"|", ">", "|-", ">-", "|+", ">+"}:
            values: list[str] = []
            index += 1
            while index < end and (lines[index].startswith(" ") or not lines[index].strip()):
                values.append(lines[index][2:] if lines[index].startswith("  ") else lines[index])
                index += 1
            separator = "\n" if raw.startswith("|") else " "
            metadata[key] = separator.join(values).strip()
            continue
        if raw == "":
            values = []
            probe = index + 1
            while probe < end and lines[probe].startswith(" ") and lines[probe].strip().startswith("-"):
                values.append(parse_scalar(lines[probe].strip()[1:].strip()))
                probe += 1
            if values:
                metadata[key] = values
                index = probe
                continue
        metadata[key] = parse_scalar(raw)
        index += 1
    body = "\n".join(lines[end + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return metadata, body, True


def render_frontmatter(metadata: Mapping[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            elif all(not isinstance(item, (dict, list)) for item in value):
                rendered = ", ".join(json.dumps(item, ensure_ascii=False) for item in value)
                lines.append(f"{key}: [{rendered}]")
            else:
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            string = str(value)
            if "\n" in string:
                lines.append(f"{key}: |-")
                lines.extend(f"  {part}" for part in string.splitlines())
            elif re.search(r"[:#\[\]{},]", string) or not string:
                lines.append(f"{key}: {json.dumps(string, ensure_ascii=False)}")
            else:
                lines.append(f"{key}: {string}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip("\n"))
    lines.append("")
    return "\n".join(lines)


def read_markdown(path: Path) -> tuple[dict[str, Any], str, bool]:
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HybridError(f"Missing Markdown file: {path}", "missing_file") from exc


def default_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "mode": "standard",
        "specs_root": "specs",
        "roadmap_path": "roadmap.md",
        "backlog_path": "backlog.md",
        "todo_name": "todo.md",
        "state_name": "state.json",
        "ticket_dir": "tickets",
        "evidence_dir": "evidence",
        "findings_dir": "findings",
        "tracker": {"kind": "local", "enabled": False},
    }


def project_from(value: str | None) -> Path:
    return Path(value or ".").resolve()


def config_path(project: Path) -> Path:
    return project / CONFIG_REL


def load_config(project: Path, required: bool = False) -> dict[str, Any]:
    path = config_path(project)
    if not path.exists():
        if required:
            raise HybridError(f"Missing project configuration: {rel_path(path, project)}", "missing_config")
        return default_config()
    value = load_json(path)
    if not isinstance(value, dict):
        raise HybridError("Project configuration must be a JSON object", "invalid_config")
    config = default_config()
    config.update(value)
    # Keep the persisted key set out of the JSON file while allowing the
    # validator to distinguish an omitted required setting from a defaulted
    # runtime value.
    config["__provided_keys"] = set(value)
    return config


def effort_id_valid(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value)) and value not in {".", ".."}


def require_effort_id(value: str | None) -> str:
    if not value or not effort_id_valid(value):
        raise HybridError("An effort ID using letters, numbers, dots, underscores, or hyphens is required", "effort_id")
    return value


def effort_path(project: Path, effort: str, config: Mapping[str, Any]) -> Path:
    effort = require_effort_id(effort)
    return safe_project_path(project, Path(str(config.get("specs_root", "specs"))) / effort)


def spec_file(effort_dir: Path) -> Path:
    return effort_dir / "spec.md"


def compact_file(effort_dir: Path) -> Path:
    return effort_dir / "change.md"


def artifact_file(effort_dir: Path, config: Mapping[str, Any], name: str) -> Path:
    if name == "todo":
        return effort_dir / str(config.get("todo_name", "todo.md"))
    if name == "state":
        return effort_dir / str(config.get("state_name", "state.json"))
    return effort_dir / name


def effort_dirs(project: Path, config: Mapping[str, Any]) -> list[Path]:
    root = safe_project_path(project, str(config.get("specs_root", "specs")))
    if not root.is_dir():
        return []
    return sorted(
        [path for path in root.iterdir() if path.is_dir() and (spec_file(path).exists() or compact_file(path).exists())],
        key=lambda path: path.name,
    )


def resolve_effort(project: Path, config: Mapping[str, Any], effort: str | None) -> Path:
    if effort:
        path = effort_path(project, effort, config)
        if not path.is_dir():
            raise HybridError(f"Effort does not exist: {effort}", "missing_effort")
        return path
    candidates = effort_dirs(project, config)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise HybridError("No effort found; provide --effort or run scaffold", "missing_effort")
    raise HybridError("More than one effort exists; provide --effort", "ambiguous_effort")


def metadata_for_effort(effort_dir: Path) -> tuple[dict[str, Any], str, Path]:
    if spec_file(effort_dir).exists():
        path = spec_file(effort_dir)
    elif compact_file(effort_dir).exists():
        path = compact_file(effort_dir)
    else:
        raise HybridError(f"Effort has no spec.md or change.md: {effort_dir}", "missing_contract")
    metadata, body, has_frontmatter = read_markdown(path)
    return metadata, body, path


def extract_defined_ids(body: str, prefix: str) -> list[str]:
    pattern = re.compile(rf"(?m)^\s*(?:\|\s*)?(?:[-*]\s*)?(?:\*\*)?({prefix}-\d{{3,}})(?:\*\*)?\b")
    return pattern.findall(body)


def extract_all_ids(text: str, prefix: str) -> list[str]:
    return re.findall(rf"\b{prefix}-\d{{3,}}\b", text)


def unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def ticket_files(effort_dir: Path, config: Mapping[str, Any]) -> list[Path]:
    directory = effort_dir / str(config.get("ticket_dir", "tickets"))
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.md"), key=lambda path: path.name)


def load_tickets(effort_dir: Path, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for path in ticket_files(effort_dir, config):
        metadata, body, has_frontmatter = read_markdown(path)
        metadata = dict(metadata)
        metadata["_path"] = path
        metadata["_body"] = body
        metadata["_frontmatter"] = has_frontmatter
        tickets.append(metadata)
    return tickets


def int_value(value: Any, default: int | None = None) -> int | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def ticket_id_num(value: str) -> int:
    match = ID_PATTERNS["TK"].match(value)
    return int(match.group(1)) if match else 10**9


def next_id_in_texts(texts: Iterable[str], prefix: str) -> str:
    maximum = 0
    scan = re.compile(rf"\b{re.escape(prefix.upper())}-(\d{{3,}})\b")
    for text in texts:
        for match in scan.finditer(text):
            maximum = max(maximum, int(match.group(1)))
    width = max(3, len(str(maximum + 1)))
    return f"{prefix.upper()}-{maximum + 1:0{width}d}"


def all_effort_texts(effort_dir: Path, config: Mapping[str, Any]) -> Iterator[str]:
    for path in effort_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".txt"}:
            try:
                yield path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue


def git_ref(project: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def git_status(project: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def empty_state(
    effort: str,
    mode: str,
    git_baseline: str | None = None,
    inventory_baseline: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "effort_id": effort,
        "mode": mode,
        "phase": "discovery",
        "status": "active",
        "revision": 0,
        "baseline": (
            {"kind": "git", "ref": git_baseline}
            if git_baseline
            else {"kind": "inventory", "ref": inventory_baseline}
        ),
        "inputs": {},
        "active_ticket": None,
        "last_evidence": None,
        "pending_questions": [],
        "blockers": [],
        "next_action": "Registrar o entendimento necessário para a próxima entrega",
        "authorization_refs": [],
    }


def state_path(effort_dir: Path, config: Mapping[str, Any]) -> Path:
    return effort_dir / str(config.get("state_name", "state.json"))


def load_state(effort_dir: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    path = state_path(effort_dir, config)
    if not path.exists():
        raise HybridError(f"Missing checkpoint: {rel_path(path, effort_dir.parent.parent)}", "missing_state")
    value = load_json(path)
    if not isinstance(value, dict):
        raise HybridError("state.json must contain an object", "invalid_state")
    return value


def current_input_fingerprints(project: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    inputs = state.get("inputs", {})
    if not isinstance(inputs, dict):
        return changed
    for name, item in inputs.items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            changed[name] = {"reason": "invalid_input_record"}
            continue
        path = item["path"]
        current = directory_fingerprint(safe_project_path(project, path), project)
        recorded = item.get("fingerprint")
        if current != recorded:
            changed[name] = {"path": path, "recorded": recorded, "current": current}
    return changed


def generated_registry(project: Path) -> dict[str, str]:
    path = project / GENERATED_REL
    if not path.exists():
        return {}
    value = load_json(path)
    return value if isinstance(value, dict) else {}


def guarded_generated_write(project: Path, path: Path, content: str, force: bool = False) -> bool:
    registry = generated_registry(project)
    relative = rel_path(path, project)
    existing_hash = sha256_file(path) if path.exists() else None
    expected_hash = registry.get(relative)
    if path.exists() and not force:
        if expected_hash is None:
            raise HybridError(
                f"Generated view already exists and is not managed: {relative}; use --force only after reviewing it",
                "write_conflict",
            )
        if existing_hash != expected_hash:
            raise HybridError(
                f"Generated view was edited since the last render: {relative}; preserve it and reconcile explicitly",
                "write_conflict",
            )
    content_hash = sha256_bytes(content.encode("utf-8"))
    if path.exists() and existing_hash == content_hash:
        return False
    atomic_write(path, content)
    registry[relative] = content_hash
    write_json(project / GENERATED_REL, registry)
    return True


def validate_config(config: Mapping[str, Any], project: Path) -> list[str]:
    errors: list[str] = []
    provided_keys = config.get("__provided_keys")
    if isinstance(provided_keys, set):
        required_keys = {
            "schema_version",
            "mode",
            "specs_root",
            "roadmap_path",
            "backlog_path",
            "todo_name",
            "state_name",
            "ticket_dir",
            "evidence_dir",
            "findings_dir",
            "tracker",
        }
        errors.extend(f"config missing {key}" for key in sorted(required_keys - provided_keys))
    if config.get("schema_version") != "1.0":
        errors.append("config.schema_version must be 1.0")
    if config.get("mode") not in {"standard", "compact", "expanded"}:
        errors.append("config.mode must be standard, compact, or expanded")
    for key in ("specs_root", "roadmap_path", "backlog_path", "todo_name", "state_name", "ticket_dir", "evidence_dir", "findings_dir"):
        if not isinstance(config.get(key), str) or not config[key]:
            errors.append(f"config.{key} must be a non-empty string")
        else:
            try:
                safe_project_path(project, config[key])
            except HybridError:
                errors.append(f"config.{key} must stay inside the project")
    tracker = config.get("tracker")
    if not isinstance(tracker, dict) or tracker.get("kind") not in {"local", "none"}:
        errors.append("config.tracker.kind must be local or none in version 1")
    elif not isinstance(tracker.get("enabled"), bool):
        errors.append("config.tracker.enabled must be a boolean")
    return errors


def validate_state(state: Mapping[str, Any], effort: str, mode: str) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "effort_id", "mode", "phase", "status", "revision", "baseline", "inputs", "next_action"}
    missing = sorted(required - set(state))
    errors.extend(f"state missing {key}" for key in missing)
    if state.get("schema_version") != "1.0":
        errors.append("state.schema_version must be 1.0")
    if state.get("effort_id") != effort:
        errors.append("state.effort_id does not match the effort directory")
    if state.get("mode") != mode:
        errors.append("state.mode does not match the contract mode")
    if state.get("phase") not in EFFORT_PHASES:
        errors.append("state.phase is invalid")
    if state.get("status") not in EFFORT_STATUSES:
        errors.append("state.status is invalid")
    baseline = state.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("kind") not in {"git", "inventory"}:
        errors.append("state.baseline must declare git or inventory")
    elif baseline.get("ref") is not None and not isinstance(baseline.get("ref"), str):
        errors.append("state.baseline.ref must be a string or null")
    if int_value(state.get("revision")) is None or int_value(state.get("revision"), -1) < 0:
        errors.append("state.revision must be a non-negative integer")
    if not isinstance(state.get("inputs"), dict):
        errors.append("state.inputs must be an object")
    elif isinstance(state.get("inputs"), dict):
        for name, item in state["inputs"].items():
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("fingerprint"), str):
                errors.append(f"state.inputs.{name} needs path and fingerprint")
    return errors


def validate_ticket(
    ticket: Mapping[str, Any],
    effort: str,
    requirements: set[str],
    acceptances: set[str],
    spec_revision: int | None,
    plan_revision: int | None,
) -> list[str]:
    errors: list[str] = []
    path = ticket.get("_path", "ticket")
    required = {
        "schema",
        "schema_version",
        "id",
        "effort",
        "type",
        "status",
        "requires",
        "requirement_refs",
        "acceptance_refs",
        "spec_revision",
        "plan_revision",
        "ticket_revision",
        "owned_areas",
        "verification_status",
    }
    errors.extend(f"{path}: missing {key}" for key in sorted(required - set(ticket)))
    if ticket.get("schema") != "hybrid/ticket":
        errors.append(f"{path}: schema must be hybrid/ticket")
    if ticket.get("schema_version") != "1.0":
        errors.append(f"{path}: schema_version must be 1.0")
    ticket_id = ticket.get("id")
    if not isinstance(ticket_id, str) or not ID_PATTERNS["TK"].match(ticket_id):
        errors.append(f"{path}: id must match TK-001")
    if ticket.get("effort") != effort:
        errors.append(f"{path}: effort does not match directory")
    if ticket.get("status") not in TICKET_STATUSES:
        errors.append(f"{path}: invalid status")
    for key in ("requires", "requirement_refs", "acceptance_refs", "owned_areas"):
        if key in ticket and not isinstance(ticket[key], list):
            errors.append(f"{path}: {key} must be a list")
    if isinstance(ticket.get("requires"), list):
        errors.extend(f"{path}: invalid blocker ID {ref}" for ref in ticket["requires"] if not isinstance(ref, str) or not ID_PATTERNS["TK"].match(ref))
    if isinstance(ticket.get("requirement_refs"), list):
        errors.extend(f"{path}: invalid requirement ID {ref}" for ref in ticket["requirement_refs"] if not isinstance(ref, str) or not ID_PATTERNS["FR"].match(ref))
    if isinstance(ticket.get("acceptance_refs"), list):
        errors.extend(f"{path}: invalid acceptance ID {ref}" for ref in ticket["acceptance_refs"] if not isinstance(ref, str) or not ID_PATTERNS["AC"].match(ref))
    if isinstance(ticket.get("owned_areas"), list):
        errors.extend(f"{path}: owned area must be a non-empty string" for area in ticket["owned_areas"] if not isinstance(area, str) or not area.strip())
    if isinstance(ticket.get("requirement_refs"), list):
        for ref in ticket["requirement_refs"]:
            if ref not in requirements:
                errors.append(f"{path}: unknown requirement reference {ref}")
    if isinstance(ticket.get("acceptance_refs"), list):
        for ref in ticket["acceptance_refs"]:
            if ref not in acceptances:
                errors.append(f"{path}: unknown acceptance reference {ref}")
    if int_value(ticket.get("spec_revision")) is None:
        errors.append(f"{path}: spec_revision must be an integer")
    if spec_revision is not None and int_value(ticket.get("spec_revision")) != spec_revision:
        errors.append(f"{path}: spec_revision does not match the contract")
    if int_value(ticket.get("plan_revision")) is None:
        errors.append(f"{path}: plan_revision must be an integer")
    if int_value(ticket.get("ticket_revision")) is None or int_value(ticket.get("ticket_revision"), -1) < 1:
        errors.append(f"{path}: ticket_revision must be a positive integer")
    if plan_revision is not None and int_value(ticket.get("plan_revision")) != plan_revision:
        errors.append(f"{path}: plan_revision does not match plan.md")
    if ticket.get("verification_status") not in VERIFICATION_STATUSES:
        errors.append(f"{path}: invalid verification_status")
    if isinstance(ticket.get("owned_areas"), list) and not ticket["owned_areas"]:
        errors.append(f"{path}: owned_areas must name at least one relevant area")
    if isinstance(ticket.get("acceptance_refs"), list) and not ticket["acceptance_refs"]:
        errors.append(f"{path}: acceptance_refs must contain at least one criterion")
    body = str(ticket.get("_body", ""))
    required_marker_groups = {
        "Objetivo": ["objetivo"],
        "Exclusões": ["exclusões", "não inclui"],
        "Leitura": ["leitura"],
        "Decisões": ["decisões"],
        "Mapa de alterações": ["mapa de alterações"],
        "Contrato": ["contrato"],
        "Exemplos": ["exemplos"],
        "Dependências": ["dependências"],
        "Sequência": ["sequência"],
        "Validação": ["validação"],
        "Condição de retorno": ["condição de retorno"],
        "Relatório de saída": ["relatório de saída"],
    }
    lower_body = body.lower()
    missing_markers = [label for label, alternatives in required_marker_groups.items() if not any(item in lower_body for item in alternatives)]
    errors.extend(f"{path}: execution package is missing section {marker}" for marker in missing_markers)
    return errors


def validate_effort(project: Path, effort_dir: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    effort = effort_dir.name
    if spec_file(effort_dir).exists() and compact_file(effort_dir).exists():
        errors.append(
            f"{rel_path(effort_dir, project)}: spec.md and change.md cannot coexist; choose one canonical profile"
        )
    try:
        metadata, body, contract_path = metadata_for_effort(effort_dir)
    except HybridError as exc:
        return {"effort": effort, "errors": [str(exc)], "warnings": []}
    if not effort_id_valid(effort):
        errors.append("effort directory name is unsafe")
    if not metadata:
        errors.append(f"{rel_path(contract_path, project)}: frontmatter is required")
    if metadata.get("schema") not in {"hybrid/spec", "hybrid/change"}:
        errors.append(f"{rel_path(contract_path, project)}: schema must be hybrid/spec or hybrid/change")
    if metadata.get("schema_version") != "1.0":
        errors.append(f"{rel_path(contract_path, project)}: schema_version must be 1.0")
    expected_schema = "hybrid/change" if contract_path.name == "change.md" else "hybrid/spec"
    if metadata.get("schema") != expected_schema:
        errors.append(f"{rel_path(contract_path, project)}: schema must be {expected_schema} for {contract_path.name}")
    mode = "compact" if contract_path.name == "change.md" else str(metadata.get("profile", "standard"))
    if mode not in {"standard", "expanded"} and contract_path.name != "change.md":
        mode = "standard"
    expected_profile = "compact" if contract_path.name == "change.md" else {"standard", "expanded"}
    if (isinstance(expected_profile, str) and metadata.get("profile") != expected_profile) or (
        isinstance(expected_profile, set) and metadata.get("profile") not in expected_profile
    ):
        expected_text = expected_profile if isinstance(expected_profile, str) else "standard or expanded"
        errors.append(f"{rel_path(contract_path, project)}: profile must be {expected_text} for {contract_path.name}")
    if metadata.get("effort_id") != effort:
        errors.append(f"{rel_path(contract_path, project)}: effort_id does not match directory")
    revision = int_value(metadata.get("revision"))
    if revision is None or revision < 1:
        errors.append(f"{rel_path(contract_path, project)}: revision must be a positive integer")
    if metadata.get("status") not in {"draft", "accepted", "superseded", "closed"}:
        errors.append(f"{rel_path(contract_path, project)}: invalid contract status")
    requirements = unique(extract_defined_ids(body, "FR"))
    acceptances = unique(extract_defined_ids(body, "AC"))
    if len(requirements) != len(extract_defined_ids(body, "FR")):
        errors.append(f"{rel_path(contract_path, project)}: duplicate requirement IDs")
    if len(acceptances) != len(extract_defined_ids(body, "AC")):
        errors.append(f"{rel_path(contract_path, project)}: duplicate acceptance IDs")
    if not requirements and not acceptances:
        warnings.append(f"{rel_path(contract_path, project)}: no FR/AC definitions found yet")
    plan_path = effort_dir / "plan.md"
    plan_revision: int | None = None
    plan_body = ""
    if plan_path.exists():
        plan_meta, plan_body, plan_frontmatter = read_markdown(plan_path)
        if not plan_frontmatter or plan_meta.get("schema") != "hybrid/plan":
            errors.append(f"{rel_path(plan_path, project)}: hybrid/plan frontmatter is required")
        if plan_meta.get("schema_version") != "1.0":
            errors.append(f"{rel_path(plan_path, project)}: schema_version must be 1.0")
        if plan_meta.get("effort_id") != effort:
            errors.append(f"{rel_path(plan_path, project)}: effort_id does not match the effort directory")
        plan_revision = int_value(plan_meta.get("revision"))
        if plan_revision is None or plan_revision < 1:
            errors.append(f"{rel_path(plan_path, project)}: revision must be a positive integer")
        if int_value(plan_meta.get("spec_revision")) != revision:
            errors.append(f"{rel_path(plan_path, project)}: spec_revision does not match contract revision")
        if plan_meta.get("status") not in {"draft", "ready", "superseded"}:
            errors.append(f"{rel_path(plan_path, project)}: invalid plan status")
    elif mode == "standard" and any((effort_dir / str(config.get("ticket_dir", "tickets"))).glob("*.md")):
        errors.append("tickets exist without plan.md")
    state_path_value = state_path(effort_dir, config)
    if state_path_value.exists():
        state = load_json(state_path_value)
        if isinstance(state, dict):
            errors.extend(validate_state(state, effort, mode))
            for name, item in state.get("inputs", {}).items() if isinstance(state.get("inputs"), dict) else []:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    try:
                        safe_project_path(project, item["path"])
                    except HybridError:
                        errors.append(f"state.inputs.{name}.path escapes the project")
        else:
            errors.append(f"{rel_path(state_path_value, project)}: state must be an object")
    else:
        errors.append(f"{rel_path(state_path_value, project)}: checkpoint is required")
    tickets = load_tickets(effort_dir, config)
    ticket_ids: set[str] = set()
    for ticket in tickets:
        ticket_id = ticket.get("id")
        if isinstance(ticket_id, str):
            if ticket_id in ticket_ids:
                errors.append(f"duplicate ticket ID {ticket_id}")
            ticket_ids.add(ticket_id)
        errors.extend(validate_ticket(ticket, effort, set(requirements), set(acceptances), revision, plan_revision))
    for ticket in tickets:
        path = ticket.get("_path", "ticket")
        for required_ticket in ticket.get("requires", []) if isinstance(ticket.get("requires"), list) else []:
            if required_ticket == ticket.get("id"):
                errors.append(f"{path}: ticket cannot require itself")
            elif required_ticket not in ticket_ids:
                errors.append(f"{path}: blocker {required_ticket} does not exist")
        if ticket.get("status") == "done" and ticket.get("verification_status") != "passed":
            errors.append(f"{path}: done ticket must have verification_status=passed")
    graph_errors, graph = graph_for_tickets(tickets)
    errors.extend(graph_errors)
    tickets_by_id = {ticket.get("id"): ticket for ticket in tickets if isinstance(ticket.get("id"), str)}
    for overlap in graph.get("owned_area_overlaps", []):
        left_id, right_id = overlap["tickets"]
        left_requires = tickets_by_id.get(left_id, {}).get("requires", [])
        right_requires = tickets_by_id.get(right_id, {}).get("requires", [])
        serialized = right_id in left_requires or left_id in right_requires
        suffix = "a dependência existente serializa a execução; revisar o escopo" if serialized else "serialize ou adicione uma dependência real"
        warnings.append(
            f"tickets {', '.join(overlap['tickets'])} share owned area(s): {', '.join(overlap['areas'])}; {suffix}"
        )
    evidence_dir = effort_dir / str(config.get("evidence_dir", "evidence"))
    evidence: list[dict[str, Any]] = []
    if evidence_dir.exists():
        for path in sorted(evidence_dir.glob("EV-*.json")):
            try:
                value = load_json(path)
            except HybridError as exc:
                errors.append(str(exc))
                continue
            if not isinstance(value, dict):
                errors.append(f"{rel_path(path, project)}: evidence must be an object")
                continue
            evidence.append(value)
            errors.extend(validate_evidence(value, set(acceptances), path, project))
            if value.get("result") == "passed" and not evidence_is_current(project, value):
                warnings.append(f"{rel_path(path, project)}: passed evidence is stale against its input fingerprints")
    evidence_ids = [item.get("id") for item in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("duplicate evidence IDs")
    for value in evidence:
        ticket_ref = value.get("ticket")
        if ticket_ref is None and mode == "compact":
            continue
        if ticket_ref not in ticket_ids:
            errors.append(f"{value.get('id')}: evidence references unknown ticket {ticket_ref}")
    findings_dir = effort_dir / str(config.get("findings_dir", "findings"))
    findings: list[dict[str, Any]] = []
    if findings_dir.exists():
        for path in sorted(findings_dir.glob("FD-*.json")):
            try:
                value = load_json(path)
            except HybridError as exc:
                errors.append(str(exc))
                continue
            if isinstance(value, dict):
                findings.append(value)
                errors.extend(validate_finding(value, path, project))
    finding_ids = [item.get("id") for item in findings]
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("duplicate finding IDs")
    todo = artifact_file(effort_dir, config, "todo")
    if todo.exists():
        if mode == "compact":
            errors.append(f"{rel_path(todo, project)}: compact efforts must keep tasks in change.md")
        else:
            expected = render_todo_content(effort_dir, config)
            if todo.read_text(encoding="utf-8") != expected:
                warnings.append(f"{rel_path(todo, project)}: generated view differs from canonical tickets")
    return {
        "effort": effort,
        "mode": mode,
        "contract": rel_path(contract_path, project),
        "revision": revision,
        "requirements": requirements,
        "acceptances": acceptances,
        "tickets": sorted(ticket_ids),
        "evidence": [item.get("id") for item in evidence],
        "findings": [item.get("id") for item in findings],
        "errors": errors,
        "warnings": warnings,
    }


def validate_evidence(value: Mapping[str, Any], acceptances: set[str], path: Path, project: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "id",
        "ticket",
        "acceptance_refs",
        "procedure",
        "execution_status",
        "environment",
        "tested_revision",
        "timestamp",
        "result",
        "observations",
        "evidence_refs",
        "limitations",
        "input_paths",
        "input_fingerprints",
    }
    errors.extend(f"{rel_path(path, project)}: missing {key}" for key in sorted(required - set(value)))
    evidence_id = value.get("id")
    if not isinstance(evidence_id, str) or not ID_PATTERNS["EV"].match(evidence_id):
        errors.append(f"{rel_path(path, project)}: id must match EV-001")
    if value.get("result") not in EVIDENCE_RESULTS:
        errors.append(f"{rel_path(path, project)}: invalid result")
    if value.get("execution_status") not in {"executed", "observed_only"}:
        errors.append(f"{rel_path(path, project)}: invalid execution_status")
    if value.get("result") in {"passed", "failed", "partial"} and value.get("execution_status") != "executed":
        errors.append(f"{rel_path(path, project)}: a result other than not_run requires execution_status=executed")
    refs = value.get("acceptance_refs")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{rel_path(path, project)}: acceptance_refs must be a non-empty list")
    elif any(ref not in acceptances for ref in refs):
        errors.append(f"{rel_path(path, project)}: unknown acceptance reference")
    if value.get("ticket") is not None and (not isinstance(value.get("ticket"), str) or not ID_PATTERNS["TK"].match(value["ticket"])):
        errors.append(f"{rel_path(path, project)}: ticket must be a TK ID or null for compact evidence")
    if not isinstance(value.get("input_paths"), list) or not isinstance(value.get("input_fingerprints"), dict):
        errors.append(f"{rel_path(path, project)}: input paths and fingerprints are required")
    return errors


def validate_finding(value: Mapping[str, Any], path: Path, project: Path) -> list[str]:
    errors: list[str] = []
    required = {"id", "effort", "origin", "gap_type", "area", "severity", "summary", "state", "dedupe_key"}
    errors.extend(f"{rel_path(path, project)}: missing {key}" for key in sorted(required - set(value)))
    finding_id = value.get("id")
    if not isinstance(finding_id, str) or not ID_PATTERNS["FD"].match(finding_id):
        errors.append(f"{rel_path(path, project)}: id must match FD-001")
    if value.get("origin") not in {"consistency", "standards", "spec", "convergence"}:
        errors.append(f"{rel_path(path, project)}: invalid origin")
    if value.get("severity") not in {"blocker", "major", "minor", "note"}:
        errors.append(f"{rel_path(path, project)}: invalid severity")
    if value.get("state") not in {"open", "in_progress", "resolved", "duplicate", "wontfix"}:
        errors.append(f"{rel_path(path, project)}: invalid state")
    if not isinstance(value.get("effort"), str) or not value.get("effort"):
        errors.append(f"{rel_path(path, project)}: effort must be a non-empty string")
    if not isinstance(value.get("summary"), str) or not value.get("summary", "").strip():
        errors.append(f"{rel_path(path, project)}: summary must be non-empty")
    if not isinstance(value.get("dedupe_key"), str) or not value.get("dedupe_key", "").strip():
        errors.append(f"{rel_path(path, project)}: dedupe_key must be non-empty")
    return errors


def graph_for_tickets(tickets: Sequence[Mapping[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    ids = {ticket.get("id") for ticket in tickets if isinstance(ticket.get("id"), str)}
    dependencies: dict[str, set[str]] = {
        ticket["id"]: set(ticket.get("requires", []))
        for ticket in tickets
        if isinstance(ticket.get("id"), str) and isinstance(ticket.get("requires", []), list)
    }
    errors: list[str] = []
    for ticket_id, blockers in dependencies.items():
        missing = sorted(blockers - ids)
        errors.extend(f"{ticket_id}: blocker {blocker} does not exist" for blocker in missing)
    indegree = {ticket_id: len(blockers & ids) for ticket_id, blockers in dependencies.items()}
    children: dict[str, set[str]] = defaultdict(set)
    for ticket_id, blockers in dependencies.items():
        for blocker in blockers & ids:
            children[blocker].add(ticket_id)
    queue = deque(sorted(ticket_id for ticket_id, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(dependencies):
        cycle_nodes = sorted(set(dependencies) - set(order))
        errors.append("ticket dependency cycle: " + ", ".join(cycle_nodes))
    by_id = {ticket.get("id"): ticket for ticket in tickets if isinstance(ticket.get("id"), str)}
    frontier: list[str] = []
    for ticket_id in order:
        ticket = by_id[ticket_id]
        if ticket.get("status") in {"ready", "in_progress", "blocked"}:
            if all(by_id[blocker].get("status") == "done" for blocker in dependencies[ticket_id] if blocker in by_id):
                if ticket.get("status") in {"ready", "in_progress"}:
                    frontier.append(ticket_id)
    overlaps: list[dict[str, Any]] = []
    ordered_ids = sorted(by_id)
    for index, left_id in enumerate(ordered_ids):
        left_areas = [Path(str(area)).as_posix().rstrip("/").lower() for area in by_id[left_id].get("owned_areas", [])]
        for right_id in ordered_ids[index + 1 :]:
            right_areas = [Path(str(area)).as_posix().rstrip("/").lower() for area in by_id[right_id].get("owned_areas", [])]
            shared: list[str] = []
            for left_area in left_areas:
                for right_area in right_areas:
                    if left_area == right_area or left_area.startswith(right_area + "/") or right_area.startswith(left_area + "/"):
                        shared.append(left_area if len(left_area) <= len(right_area) else right_area)
            if shared:
                overlaps.append({"tickets": [left_id, right_id], "areas": sorted(unique(shared))})
    return errors, {
        "order": order,
        "frontier": frontier,
        "dependencies": {key: sorted(value) for key, value in dependencies.items()},
        "owned_area_overlaps": overlaps,
    }


def render_todo_content(effort_dir: Path, config: Mapping[str, Any]) -> str:
    tickets = load_tickets(effort_dir, config)
    _, graph = graph_for_tickets(tickets)
    by_id = {ticket.get("id"): ticket for ticket in tickets if isinstance(ticket.get("id"), str)}
    lines = [
        "# TODO gerado",
        "",
        "<!-- GENERATED: hybrid tickets are the canonical source. Edit the ticket, then render again. -->",
        "",
    ]
    for ticket_id in graph["order"]:
        ticket = by_id[ticket_id]
        status = str(ticket.get("status", "draft"))
        mark = "x" if status == "done" else " "
        title_match = re.search(r"^#\s+(.+)$", str(ticket.get("_body", "")), re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ticket_id
        lines.append(f"## [{mark}] {ticket_id} — {title}")
        requires = ticket.get("requires", [])
        lines.append(f"Status: `{status}` | Bloqueado por: {', '.join(requires) if requires else 'nenhum'}")
        lines.append("")
        tasks = re.findall(r"(?m)^\s*-\s*\[([ xX])\]\s+(.+)$", str(ticket.get("_body", "")))
        if tasks:
            for task_mark, task_text in tasks:
                lines.append(f"- [{task_mark}] {task_text}")
        else:
            lines.append(f"- [{'x' if status == 'done' else ' '}] executar a sequência canônica do ticket")
        lines.append("")
    if not graph["order"]:
        lines.append("Nenhum ticket canônico foi criado para este esforço.")
        lines.append("")
    return "\n".join(lines)


def contract_title(contract_body: str, fallback: str) -> str:
    match = re.search(r"(?m)^#\s+(.+)$", contract_body)
    return match.group(1).strip() if match else fallback


def render_backlog_content(project: Path, config: Mapping[str, Any]) -> str:
    lines = [
        "# Backlog gerado",
        "",
        "<!-- GENERATED: roadmap candidates and effort checkpoints are canonical sources. -->",
        "",
        "| ID | Título/resultado | Origem | Prioridade | Fase | Estado | Tickets | Próxima ação |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    known_efforts = {directory.name for directory in effort_dirs(project, config)}
    roadmap = safe_project_path(project, str(config.get("roadmap_path", "roadmap.md")))
    if roadmap.exists():
        for line in roadmap.read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 5 or not re.fullmatch(r"CAND-[0-9]{3,}", cells[0]):
                continue
            promoted = cells[5] if len(cells) > 5 else "—"
            if promoted in known_efforts:
                continue
            candidate_title = cells[1].replace("|", "\\|")
            priority = cells[3] or "—"
            state = cells[4] or "candidate"
            lines.append(
                f"| `{cells[0]}` | {candidate_title} | `roadmap` | `{priority}` | `roadmap` | `{state}` | — | Promover após prontidão |"
            )
    has_effort_row = False
    for directory in effort_dirs(project, config):
        _metadata, body, contract = metadata_for_effort(directory)
        state_path_value = state_path(directory, config)
        state = load_json(state_path_value) if state_path_value.exists() else {}
        tickets = load_tickets(directory, config)
        ticket_progress = (
            f"{sum(ticket.get('status') == 'done' for ticket in tickets)}/{len(tickets)}"
            if tickets
            else "—"
        )
        title = contract_title(body, directory.name)
        escaped_title = title.replace("|", "\\|")
        next_action = str(state.get("next_action", ""))
        next_action = next_action.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{directory.name}` | {escaped_title} | `effort` | `—` | "
            f"`{state.get('phase', 'discovery')}` | `{state.get('status', 'active')}` | `{ticket_progress}` | {next_action} |"
        )
        has_effort_row = True
    if not has_effort_row and not any("`CAND-" in line for line in lines):
        lines.append("| — | Nenhum esforço promovido | — | — | — | — | — | — |")
    lines.append("")
    return "\n".join(lines)


def render_verification_content(effort_dir: Path, config: Mapping[str, Any]) -> str:
    evidence_dir = effort_dir / str(config.get("evidence_dir", "evidence"))
    records: list[dict[str, Any]] = []
    if evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("EV-*.json")):
            value = load_json(path)
            if isinstance(value, dict):
                records.append(value)
    lines = [
        "# Verification",
        "",
        "<!-- GENERATED from evidence/*.json. Evidence records are canonical. -->",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"## {record.get('id', 'EV-???')} — {record.get('result', 'not_run')}",
                "",
                f"- Ticket: `{record.get('ticket') or '—'}`",
                f"- Acceptance: {', '.join(f'`{item}`' for item in record.get('acceptance_refs', []))}",
                f"- Procedure: `{record.get('procedure', '')}`",
                f"- Execution: `{record.get('execution_status', 'observed_only')}`",
                f"- Environment: {record.get('environment', '')}",
                f"- Tested revision: `{record.get('tested_revision', '')}`",
                f"- Timestamp: `{record.get('timestamp', '')}`",
                f"- Observations: {record.get('observations', '')}",
                f"- Evidence refs: {', '.join(f'`{item}`' for item in record.get('evidence_refs', [])) or 'none'}",
                f"- Limitations: {record.get('limitations', '') or 'none recorded'}",
                "",
            ]
        )
    if not records:
        lines.append("Nenhuma execução foi registrada.")
        lines.append("")
    return "\n".join(lines)


def add_paths_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--effort", help="Effort ID")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def emit(value: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(value, dict) and "message" in value:
        print(value["message"])
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def run_init(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    project.mkdir(parents=True, exist_ok=True)
    path = config_path(project)
    changed = False
    if path.exists():
        config = load_config(project, required=True)
    else:
        config = default_config()
        if args.mode:
            config["mode"] = args.mode
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, config)
        changed = True
    return {
        "outcome": "completed",
        "project": str(project),
        "config": rel_path(path, project),
        "mode": config.get("mode"),
        "changed": changed,
        "next_action": "Use scaffold para criar um esforço ou install para adotar as skills em outro projeto",
    }


def load_template(relative: str, fallback: str) -> str:
    path = SHARED_ROOT / "templates" / relative
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def run_scaffold(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    effort = require_effort_id(args.effort)
    mode = args.mode or str(config.get("mode", "standard"))
    if mode not in {"standard", "compact", "expanded"}:
        raise HybridError("mode must be standard, compact, or expanded", "mode")
    directory = effort_path(project, effort, config)
    baseline = git_ref(project)
    inventory_baseline = None if baseline else directory_fingerprint(project, project)
    directory.mkdir(parents=True, exist_ok=True)
    contract = compact_file(directory) if mode == "compact" else spec_file(directory)
    other_contract = spec_file(directory) if contract.name == "change.md" else compact_file(directory)
    if other_contract.exists():
        raise HybridError(
            f"Effort already has a different contract: {rel_path(other_contract, project)}; reconcile the profile explicitly",
            "contract_conflict",
        )
    if contract.exists() and not args.force:
        raise HybridError(f"Contract already exists: {rel_path(contract, project)}", "write_conflict")
    title = args.title or effort.replace("-", " ").title()
    if mode == "compact":
        body = load_template("compact/change.md", "# Change: [title]\n")
        content = body.replace("[TITLE]", title).replace("[title]", title)
    else:
        body = load_template("standard/spec.md", "# Specification: [title]\n")
        content = body.replace("[TITLE]", title).replace("[title]", title)
    metadata = {
        "schema": "hybrid/change" if mode == "compact" else "hybrid/spec",
        "schema_version": "1.0",
        "effort_id": effort,
        "revision": 1,
        "status": "draft",
        "profile": mode,
    }
    atomic_write(contract, render_frontmatter(metadata, content))
    state = empty_state(
        effort,
        mode,
        git_baseline=baseline,
        inventory_baseline=inventory_baseline,
    )
    state["inputs"] = {
        "contract": {
            "path": rel_path(contract, project),
            "revision": 1,
            "fingerprint": sha256_file(contract),
        }
    }
    write_json(state_path(directory, config), state)
    if mode != "compact":
        (directory / str(config.get("ticket_dir", "tickets"))).mkdir(exist_ok=True)
        (directory / str(config.get("evidence_dir", "evidence"))).mkdir(exist_ok=True)
        (directory / str(config.get("findings_dir", "findings"))).mkdir(exist_ok=True)
    return {
        "outcome": "completed",
        "effort": effort,
        "mode": mode,
        "contract": rel_path(contract, project),
        "state": rel_path(state_path(directory, config), project),
        "next_action": "Preencher o contrato; em perfil padrão seguir com plan e slice, em compacto implementar após a validação local",
    }


def run_next_id(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    prefix = args.prefix.upper()
    value = next_id_in_texts(all_effort_texts(directory, config), prefix)
    return {"outcome": "completed", "effort": directory.name, "prefix": prefix, "next": value}


def run_validate(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project, required=args.require_config)
    errors = validate_config(config, project)
    warnings: list[str] = []
    efforts: list[dict[str, Any]] = []
    directories = [resolve_effort(project, config, args.effort)] if args.effort else effort_dirs(project, config)
    if not directories and args.effort:
        raise HybridError("Requested effort was not found", "missing_effort")
    for directory in directories:
        result = validate_effort(project, directory, config)
        efforts.append(result)
        errors.extend(f"{directory.name}: {error}" for error in result.get("errors", []))
        warnings.extend(f"{directory.name}: {warning}" for warning in result.get("warnings", []))
    result = {
        "outcome": "completed" if not errors else "failed",
        "ok": not errors,
        "project": str(project),
        "errors": errors,
        "warnings": warnings,
        "efforts": efforts,
        "checks": {
            "config": not validate_config(config, project),
            "effort_count": len(directories),
            "schema_source": rel_path(SHARED_ROOT / "schemas", project) if (SHARED_ROOT / "schemas").exists() else None,
        },
    }
    return result


def run_graph(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    tickets = load_tickets(directory, config)
    errors, graph = graph_for_tickets(tickets)
    return {"outcome": "completed" if not errors else "failed", "ok": not errors, "effort": directory.name, "errors": errors, **graph}


def run_render(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    view = args.view
    changed: list[str] = []
    targets: list[tuple[Path, str]] = []
    if view in {"todo", "all"}:
        directory = resolve_effort(project, config, args.effort)
        _metadata, _body, contract = metadata_for_effort(directory)
        if contract.name == "change.md":
            if view == "todo":
                raise HybridError("Compact efforts keep tasks in change.md and do not generate todo.md", "compact_projection")
        else:
            graph_errors, _graph = graph_for_tickets(load_tickets(directory, config))
            if graph_errors:
                raise HybridError("Cannot render todo.md while the ticket graph is invalid: " + "; ".join(graph_errors), "invalid_graph")
            targets.append((artifact_file(directory, config, "todo"), render_todo_content(directory, config)))
    if view in {"backlog", "all"}:
        targets.append((safe_project_path(project, str(config.get("backlog_path", "backlog.md"))), render_backlog_content(project, config)))
    for path, content in targets:
        if guarded_generated_write(project, path, content, args.force):
            changed.append(rel_path(path, project))
    return {"outcome": "completed", "changed": changed, "generated_registry": rel_path(project / GENERATED_REL, project)}


def run_start(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    baseline = git_ref(project)
    directory: Path | None = None
    state: dict[str, Any] | None = None
    changed_inputs: dict[str, Any] = {}
    untracked_inputs: dict[str, str] = {}
    if args.effort or effort_dirs(project, config):
        directory = resolve_effort(project, config, args.effort)
        state = load_state(directory, config)
        changed_inputs = current_input_fingerprints(project, state)
        tracked_paths = {
            str(item.get("path"))
            for item in state.get("inputs", {}).values()
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        untracked_inputs = {
            name: path
            for name, path in canonical_effort_inputs(project, directory).items()
            if path not in tracked_paths
        }
    if changed_inputs:
        next_action = "Executar invalidate --write antes de continuar"
    elif untracked_inputs:
        next_action = "Registrar os insumos canônicos no checkpoint antes de continuar"
    else:
        next_action = (state or {}).get("next_action", "Classificar a demanda e iniciar descoberta")
    return {
        "outcome": "completed",
        "project": str(project),
        "git_baseline": baseline,
        "inventory_fingerprint": None if baseline else directory_fingerprint(project, project),
        "working_changes": git_status(project),
        "effort": directory.name if directory else None,
        "state": state,
        "changed_inputs": changed_inputs,
        "untracked_inputs": untracked_inputs,
        "next_action": next_action,
    }


def run_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    path = state_path(directory, config)
    state = load_state(directory, config)
    current_revision = int_value(state.get("revision"), -1)
    if args.expected_revision is not None and current_revision != args.expected_revision:
        raise HybridError(
            f"Checkpoint conflict: expected revision {args.expected_revision}, current revision {current_revision}",
            "checkpoint_conflict",
        )
    if args.phase and args.phase not in EFFORT_PHASES:
        raise HybridError("Invalid effort phase", "phase")
    if args.status and args.status not in EFFORT_STATUSES:
        raise HybridError("Invalid effort status", "status")
    updated = dict(state)
    if args.phase:
        updated["phase"] = args.phase
    if args.status:
        updated["status"] = args.status
    if args.next_action is not None:
        updated["next_action"] = args.next_action
    if args.active_ticket is not None:
        updated["active_ticket"] = args.active_ticket
    if args.last_evidence is not None:
        updated["last_evidence"] = args.last_evidence
    if args.pending_question:
        updated["pending_questions"] = list(args.pending_question)
    if args.blocker:
        updated["blockers"] = list(args.blocker)
    if args.input:
        inputs = dict(updated.get("inputs", {})) if isinstance(updated.get("inputs"), dict) else {}
        for raw in args.input:
            if "=" not in raw:
                raise HybridError("Each --input must use name=path", "input")
            name, input_path = raw.split("=", 1)
            name = name.strip()
            input_path = input_path.strip()
            if not name or not input_path:
                raise HybridError("Each --input must use a non-empty name=path", "input")
            target = safe_project_path(project, input_path)
            normalized = rel_path(target, project)
            item: dict[str, Any] = {
                "path": normalized,
                "fingerprint": directory_fingerprint(target, project),
            }
            if target.is_file():
                try:
                    metadata, _body, has_frontmatter = read_markdown(target)
                except HybridError:
                    metadata, has_frontmatter = {}, False
                if has_frontmatter and int_value(metadata.get("revision")) is not None:
                    item["revision"] = int_value(metadata.get("revision"))
            inputs[name] = item
        updated["inputs"] = inputs
    updated["revision"] = current_revision + 1
    updated["updated_at"] = now_iso()
    atomic_write(path, json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"outcome": "completed", "effort": directory.name, "revision": updated["revision"], "state": rel_path(path, project)}


def input_paths_from_args(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if getattr(args, "path", None):
        values.extend(args.path)
    if getattr(args, "paths", None):
        values.extend(args.paths)
    return unique(Path(value).as_posix() for value in values)


def evidence_is_current(project: Path, record: Mapping[str, Any]) -> bool:
    record_paths = record.get("input_paths", [])
    record_fingerprints = record.get("input_fingerprints", {})
    if not isinstance(record_paths, list) or not isinstance(record_fingerprints, dict) or not record_paths:
        return False
    normalized_paths = [Path(str(item)).as_posix() for item in record_paths]
    try:
        _, current = fingerprint_paths(project, normalized_paths)
    except HybridError:
        return False
    return all(current.get(path) == record_fingerprints.get(path) for path in normalized_paths)


def evidence_input_paths(
    project: Path,
    effort_dir: Path,
    explicit_paths: Sequence[str],
) -> list[str]:
    paths = list(explicit_paths)
    _metadata, _body, contract = metadata_for_effort(effort_dir)
    paths.append(rel_path(contract, project))
    plan = effort_dir / "plan.md"
    if plan.exists():
        paths.append(rel_path(plan, project))
    return unique(Path(path).as_posix() for path in paths)


def canonical_effort_inputs(project: Path, effort_dir: Path) -> dict[str, str]:
    _metadata, _body, contract = metadata_for_effort(effort_dir)
    inputs = {"contract": rel_path(contract, project)}
    plan = effort_dir / "plan.md"
    if plan.exists():
        inputs["plan"] = rel_path(plan, project)
    return inputs


def run_invalidate(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    state = load_state(directory, config)
    changed_inputs = current_input_fingerprints(project, state)
    evidence_dir = directory / str(config.get("evidence_dir", "evidence"))
    stale: list[str] = []
    updated_records: list[str] = []
    stale_tickets: set[str] = set()
    if evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("EV-*.json")):
            record = load_json(path)
            if not isinstance(record, dict) or record.get("result") == "stale":
                continue
            record_paths = record.get("input_paths", [])
            record_fingerprints = record.get("input_fingerprints", {})
            if not isinstance(record_paths, list) or not isinstance(record_fingerprints, dict):
                continue
            if not evidence_is_current(project, record):
                stale.append(str(record.get("id", path.stem)))
                if isinstance(record.get("ticket"), str):
                    stale_tickets.add(record["ticket"])
                if args.write:
                    record["result"] = "stale"
                    record["limitations"] = (str(record.get("limitations", "")).rstrip() + " Evidence invalidated because an input changed.").strip()
                    write_json(path, record)
                    updated_records.append(str(record.get("id", path.stem)))
    updated_tickets: list[str] = []
    if args.write and stale_tickets:
        for ticket in load_tickets(directory, config):
            if ticket.get("id") not in stale_tickets:
                continue
            metadata = {key: value for key, value in ticket.items() if not key.startswith("_")}
            metadata["verification_status"] = "stale"
            if metadata.get("status") in {"verified", "done"}:
                metadata["status"] = "in_progress"
            metadata["ticket_revision"] = int_value(metadata.get("ticket_revision"), 0) + 1
            metadata["last_update"] = "Evidence invalidated after an input changed."
            atomic_write(ticket["_path"], render_frontmatter(metadata, str(ticket.get("_body", ""))))
            updated_tickets.append(str(ticket.get("id")))
    if args.write and (changed_inputs or stale):
        updated_state = dict(state)
        updated_state["revision"] = int_value(state.get("revision"), 0) + 1
        updated_state["last_invalidation"] = {"timestamp": now_iso(), "inputs": changed_inputs, "evidence": stale}
        for name, item in updated_state.get("inputs", {}).items():
            if name in changed_inputs and isinstance(item, dict):
                target = safe_project_path(project, item["path"])
                item["fingerprint"] = directory_fingerprint(target, project)
                if target.is_file():
                    try:
                        metadata, _body, has_frontmatter = read_markdown(target)
                    except HybridError:
                        metadata, has_frontmatter = {}, False
                    if has_frontmatter and int_value(metadata.get("revision")) is not None:
                        item["revision"] = int_value(metadata.get("revision"))
        updated_state["updated_at"] = now_iso()
        write_json(state_path(directory, config), updated_state)
    return {
        "outcome": "completed",
        "effort": directory.name,
        "changed_inputs": changed_inputs,
        "stale_evidence": stale,
        "updated_records": updated_records,
        "updated_tickets": updated_tickets,
        "written": bool(args.write),
        "next_action": "Reexecutar as verificações afetadas" if stale else "Nenhuma evidência afetada detectada",
    }


def run_evidence_add(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    _metadata, contract_body, contract_path = metadata_for_effort(directory)
    tickets = load_tickets(directory, config)
    ticket: dict[str, Any] | None = None
    if args.ticket:
        matches = [item for item in tickets if item.get("id") == args.ticket]
        if len(matches) != 1:
            raise HybridError(f"Ticket not found or not unique: {args.ticket}", "missing_ticket")
        ticket = matches[0]
    elif contract_path.name != "change.md":
        raise HybridError("A standard evidence record requires --ticket", "missing_ticket")
    refs = [item.strip() for item in args.acceptance_refs.split(",") if item.strip()]
    if not refs:
        raise HybridError("At least one acceptance reference is required", "evidence")
    known_acceptances = set(extract_defined_ids(contract_body, "AC"))
    unknown_acceptances = sorted(set(refs) - known_acceptances)
    if unknown_acceptances:
        raise HybridError(f"Unknown acceptance reference(s): {', '.join(unknown_acceptances)}", "evidence")
    if ticket is not None:
        ticket_acceptances = set(ticket.get("acceptance_refs", []))
        outside_ticket = sorted(set(refs) - ticket_acceptances)
        if outside_ticket:
            raise HybridError(
                f"Evidence references acceptance(s) outside {args.ticket}: {', '.join(outside_ticket)}",
                "evidence",
            )
    result = args.result
    execution_status = "executed" if args.executed else "observed_only"
    if result in {"passed", "failed", "partial"} and not args.executed:
        raise HybridError("A passed, failed, or partial result requires --executed", "evidence_not_executed")
    explicit_paths = input_paths_from_args(args)
    if result in {"passed", "failed", "partial"} and not explicit_paths:
        raise HybridError("An executed evidence result requires at least one explicit --path", "evidence_input")
    for input_path in explicit_paths:
        if not safe_project_path(project, input_path).exists() and result != "not_run":
            raise HybridError(f"Evidence input does not exist: {input_path}", "missing_input")
    paths = evidence_input_paths(project, directory, explicit_paths)
    tested_revision, fingerprints = fingerprint_paths(project, paths)
    evidence_dir = directory / str(config.get("evidence_dir", "evidence"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    records = [load_json(path) for path in evidence_dir.glob("EV-*.json")]
    texts = [json.dumps(value, ensure_ascii=False) for value in records if isinstance(value, dict)]
    evidence_id = next_id_in_texts(texts, "EV")
    record = {
        "id": evidence_id,
        "ticket": args.ticket,
        "acceptance_refs": refs,
        "procedure": args.procedure,
        "execution_status": execution_status,
        "environment": args.environment or f"OS={platform.platform()}; Python={platform.python_version()}",
        "tested_revision": tested_revision,
        "timestamp": now_iso(),
        "result": result,
        "observations": args.observations or "",
        "evidence_refs": [item for item in (args.evidence_ref or []) if item],
        "limitations": args.limitations or "",
        "input_paths": paths,
        "input_fingerprints": fingerprints,
    }
    errors = validate_evidence(record, known_acceptances, evidence_dir / f"{evidence_id}.json", project)
    if errors:
        raise HybridError("; ".join(errors), "evidence")
    target = evidence_dir / f"{evidence_id}.json"
    verification = directory / "verification.md"
    verification_content = render_verification_content_with_extra(directory, config, record)
    if verification.exists() and not args.force:
        registry = generated_registry(project)
        old_hash = registry.get(rel_path(verification, project))
        if old_hash is None or sha256_file(verification) != old_hash:
            raise HybridError(
                f"verification.md is user-edited or unmanaged: {rel_path(verification, project)}",
                "write_conflict",
            )
    write_json(target, record)
    guarded_generated_write(project, verification, verification_content, args.force)
    return {
        "outcome": "completed",
        "effort": directory.name,
        "ticket": args.ticket,
        "evidence": evidence_id,
        "result": result,
        "execution_status": execution_status,
        "tested_revision": tested_revision,
        "verification": rel_path(verification, project),
    }


def render_verification_content_with_extra(effort_dir: Path, config: Mapping[str, Any], extra: Mapping[str, Any]) -> str:
    # The new record is not written yet, so render it in the same canonical order.
    records: list[dict[str, Any]] = []
    evidence_dir = effort_dir / str(config.get("evidence_dir", "evidence"))
    if evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("EV-*.json")):
            value = load_json(path)
            if isinstance(value, dict):
                records.append(value)
    records.append(dict(extra))
    records.sort(key=lambda item: str(item.get("id", "")))
    lines = [
        "# Verification",
        "",
        "<!-- GENERATED from evidence/*.json. Evidence records are canonical. -->",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"## {record.get('id', 'EV-???')} — {record.get('result', 'not_run')}",
                "",
                f"- Ticket: `{record.get('ticket') or '—'}`",
                f"- Acceptance: {', '.join(f'`{item}`' for item in record.get('acceptance_refs', []))}",
                f"- Procedure: `{record.get('procedure', '')}`",
                f"- Execution: `{record.get('execution_status', 'observed_only')}`",
                f"- Environment: {record.get('environment', '')}",
                f"- Tested revision: `{record.get('tested_revision', '')}`",
                f"- Timestamp: `{record.get('timestamp', '')}`",
                f"- Observations: {record.get('observations', '')}",
                f"- Evidence refs: {', '.join(f'`{item}`' for item in record.get('evidence_refs', [])) or 'none'}",
                f"- Limitations: {record.get('limitations', '') or 'none recorded'}",
                "",
            ]
        )
    return "\n".join(lines)


def run_ticket_update(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    tickets = load_tickets(directory, config)
    matches = [ticket for ticket in tickets if ticket.get("id") == args.ticket]
    if len(matches) != 1:
        raise HybridError(f"Ticket not found or not unique: {args.ticket}", "missing_ticket")
    ticket = matches[0]
    old_status = ticket.get("status")
    if args.status and args.status not in TICKET_STATUSES:
        raise HybridError("Invalid ticket status", "ticket_status")
    requested_verification = args.verification_status or ticket.get("verification_status")
    if args.status in {"verified", "done"} or requested_verification == "passed":
        evidence_dir = directory / str(config.get("evidence_dir", "evidence"))
        passed_refs: set[str] = set()
        if evidence_dir.is_dir():
            for evidence_path in evidence_dir.glob("EV-*.json"):
                evidence = load_json(evidence_path)
                if (
                    isinstance(evidence, dict)
                    and evidence.get("ticket") == args.ticket
                    and evidence.get("result") == "passed"
                    and evidence_is_current(project, evidence)
                ):
                    passed_refs.update(evidence.get("acceptance_refs", []))
        required_refs = set(ticket.get("acceptance_refs", []))
        if not required_refs.issubset(passed_refs):
            missing = ", ".join(sorted(required_refs - passed_refs))
            raise HybridError(f"Current passed evidence is missing for: {missing}", "ticket_gate")
    metadata = {key: value for key, value in ticket.items() if not key.startswith("_")}
    if args.status:
        metadata["status"] = args.status
    if args.verification_status:
        if args.verification_status not in VERIFICATION_STATUSES:
            raise HybridError("Invalid verification status", "verification_status")
        metadata["verification_status"] = args.verification_status
    if args.note:
        metadata["last_update"] = args.note
    metadata["ticket_revision"] = int_value(metadata.get("ticket_revision"), 0) + 1
    body = str(ticket.get("_body", ""))
    atomic_write(ticket["_path"], render_frontmatter(metadata, body))
    return {
        "outcome": "completed",
        "effort": directory.name,
        "ticket": args.ticket,
        "from": old_status,
        "to": metadata.get("status"),
        "verification_status": metadata.get("verification_status"),
    }


def run_finding_add(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    findings_dir = directory / str(config.get("findings_dir", "findings"))
    findings_dir.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    for path in findings_dir.glob("FD-*.json"):
        value = load_json(path)
        if isinstance(value, dict):
            existing.append(value)
    discriminator = args.discriminator or args.source_ref or ""
    dedupe_key = "|".join([directory.name, args.origin, args.gap_type, args.area, discriminator])
    for value in existing:
        if value.get("dedupe_key") == dedupe_key and value.get("state") not in {"resolved", "wontfix", "duplicate"}:
            return {
                "outcome": "completed",
                "created": False,
                "deduplicated": True,
                "existing": value.get("id"),
                "dedupe_key": dedupe_key,
            }
    finding_id = next_id_in_texts((json.dumps(value, ensure_ascii=False) for value in existing), "FD")
    value = {
        "id": finding_id,
        "effort": directory.name,
        "origin": args.origin,
        "source_ref": args.source_ref or "",
        "gap_type": args.gap_type,
        "area": args.area,
        "severity": args.severity,
        "summary": args.summary,
        "evidence_location": args.evidence_location or "",
        "consequence": args.consequence or "",
        "state": "open",
        "fix_ticket": args.fix_ticket,
        "dedupe_key": dedupe_key,
        "created_at": now_iso(),
    }
    errors = validate_finding(value, findings_dir / f"{finding_id}.json", project)
    if errors:
        raise HybridError("; ".join(errors), "finding")
    write_json(findings_dir / f"{finding_id}.json", value)
    return {"outcome": "completed", "created": True, "finding": finding_id, "dedupe_key": dedupe_key}


def run_dedupe(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    findings_dir = directory / str(config.get("findings_dir", "findings"))
    groups: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    if findings_dir.is_dir():
        for path in sorted(findings_dir.glob("FD-*.json")):
            value = load_json(path)
            if isinstance(value, dict) and value.get("dedupe_key"):
                groups[str(value["dedupe_key"])].append((path, value))
    duplicates: list[dict[str, Any]] = []
    for key, entries in groups.items():
        open_entries = [entry for entry in entries if entry[1].get("state") not in {"resolved", "wontfix", "duplicate"}]
        if len(open_entries) <= 1:
            continue
        canonical_path, canonical = sorted(open_entries, key=lambda pair: str(pair[1].get("id")))[0]
        for path, value in open_entries[1:]:
            item = {"duplicate": value.get("id"), "canonical": canonical.get("id"), "dedupe_key": key}
            duplicates.append(item)
            if args.write:
                value["state"] = "duplicate"
                value["duplicate_of"] = canonical.get("id")
                write_json(path, value)
    return {"outcome": "completed", "duplicates": duplicates, "written": bool(args.write)}


def find_ticket_for_ref(tickets: Sequence[Mapping[str, Any]], ref: str, key: str) -> list[str]:
    return [str(ticket.get("id")) for ticket in tickets if ref in ticket.get(key, [])]


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    validation = validate_effort(project, directory, config)
    metadata, body, contract = metadata_for_effort(directory)
    requirements = set(extract_defined_ids(body, "FR"))
    acceptances = set(extract_defined_ids(body, "AC"))
    tickets = load_tickets(directory, config)
    findings: list[dict[str, Any]] = []
    if args.mode == "consistency":
        for ref in sorted(requirements):
            if not find_ticket_for_ref(tickets, ref, "requirement_refs"):
                findings.append({"origin": "consistency", "gap_type": "requirement_without_ticket", "source_ref": ref, "severity": "blocker", "summary": f"{ref} has no ticket"})
        for ref in sorted(acceptances):
            if not find_ticket_for_ref(tickets, ref, "acceptance_refs"):
                findings.append({"origin": "consistency", "gap_type": "acceptance_without_ticket", "source_ref": ref, "severity": "blocker", "summary": f"{ref} has no ticket"})
        for ticket in tickets:
            body_text = str(ticket.get("_body", ""))
            if "validação" not in body_text.lower() or "comando" not in body_text.lower():
                findings.append({"origin": "consistency", "gap_type": "ticket_without_validation", "source_ref": str(ticket.get("id")), "severity": "major", "summary": f"{ticket.get('id')} lacks an executable validation procedure"})
        graph_errors, _ = graph_for_tickets(tickets)
        for error in graph_errors:
            findings.append({"origin": "consistency", "gap_type": "graph_invalid", "source_ref": "graph", "severity": "blocker", "summary": error})
    else:
        evidence_dir = directory / str(config.get("evidence_dir", "evidence"))
        passed_refs: set[str] = set()
        evidence_records: list[dict[str, Any]] = []
        if evidence_dir.is_dir():
            for path in evidence_dir.glob("EV-*.json"):
                value = load_json(path)
                if isinstance(value, dict):
                    evidence_records.append(value)
                    if value.get("result") == "passed" and evidence_is_current(project, value):
                        passed_refs.update(value.get("acceptance_refs", []))
        for ref in sorted(acceptances - passed_refs):
            findings.append({"origin": "convergence", "gap_type": "acceptance_without_current_pass", "source_ref": ref, "severity": "blocker", "summary": f"{ref} has no current passed evidence"})
        for ticket in tickets:
            if ticket.get("status") == "done" and ticket.get("verification_status") != "passed":
                findings.append({"origin": "convergence", "gap_type": "done_without_verification", "source_ref": str(ticket.get("id")), "severity": "blocker", "summary": f"{ticket.get('id')} is done without passed verification"})
        if not findings and validation.get("warnings"):
            for warning in validation["warnings"]:
                findings.append({"origin": "convergence", "gap_type": "review_warning", "source_ref": "validation", "severity": "minor", "summary": warning})
    created: list[Any] = []
    if args.write:
        for finding in findings:
            namespace = argparse.Namespace(
                project=args.project,
                effort=directory.name,
                origin=finding["origin"],
                source_ref=finding.get("source_ref", ""),
                gap_type=finding["gap_type"],
                area=args.area or "artifact",
                severity=finding["severity"],
                summary=finding["summary"],
                discriminator=finding.get("source_ref", ""),
                evidence_location=rel_path(contract, project),
                consequence="See the linked contract or evidence before advancing the gate.",
                fix_ticket=None,
            )
            created.append(run_finding_add(namespace))
    return {
        "outcome": "completed",
        "mode": args.mode,
        "effort": directory.name,
        "validation": {"errors": validation.get("errors", []), "warnings": validation.get("warnings", [])},
        "findings": findings,
        "created": created,
        "written": bool(args.write),
    }


def heading_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"(?ims)^\s*##\s+[^\n]*{re.escape(heading)}[^\n]*$")
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"(?m)^\s*##\s+", body[start:])
    end = start + next_heading.start() if next_heading else len(body)
    return body[start:end].strip()


def run_package(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    config = load_config(project)
    directory = resolve_effort(project, config, args.effort)
    tickets = load_tickets(directory, config)
    match = [ticket for ticket in tickets if ticket.get("id") == args.ticket]
    if len(match) != 1:
        raise HybridError(f"Ticket not found: {args.ticket}", "missing_ticket")
    ticket = match[0]
    validation = validate_effort(project, directory, config)
    errors = list(validation.get("errors", []))
    contract_metadata, _contract_body, _contract_path = metadata_for_effort(directory)
    if contract_metadata.get("status") != "accepted":
        errors.append("contract must have status=accepted before a ticket is ready")
    plan_path = directory / "plan.md"
    if plan_path.exists():
        plan_metadata, _plan_body, _plan_frontmatter = read_markdown(plan_path)
        if plan_metadata.get("status") != "ready":
            errors.append("plan.md must have status=ready before a ticket is ready")
    state = load_state(directory, config)
    if state.get("status") != "active":
        errors.append("effort checkpoint must have status=active before a ticket is ready")
    changed_inputs = current_input_fingerprints(project, state)
    tracked_paths = {
        str(item.get("path"))
        for item in state.get("inputs", {}).values()
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    untracked_inputs = {
        name: path
        for name, path in canonical_effort_inputs(project, directory).items()
        if path not in tracked_paths
    }
    blockers = []
    dependency_states: list[dict[str, Any]] = []
    required_blockers = ticket.get("requires", []) if isinstance(ticket.get("requires", []), list) else []
    for blocker in required_blockers:
        predecessor = next((item for item in tickets if item.get("id") == blocker), None)
        dependency_states.append(
            {
                "ticket": blocker,
                "status": predecessor.get("status") if predecessor else "missing",
                "verification_status": predecessor.get("verification_status") if predecessor else None,
            }
        )
        if not predecessor or predecessor.get("status") != "done":
            blockers.append(blocker)
    package = {
        "identity": {
            "effort_id": directory.name,
            "ticket_id": args.ticket,
            "ticket_type": ticket.get("type"),
            "ticket_status": ticket.get("status"),
            "ticket_revision": ticket.get("ticket_revision", 1),
            "spec_revision": ticket.get("spec_revision"),
            "plan_revision": ticket.get("plan_revision"),
            "checkpoint_revision": state.get("revision"),
            "baseline": state.get("baseline"),
        },
        "objective_and_limits": {
            "body": str(ticket.get("_body", "")),
            "requirement_refs": ticket.get("requirement_refs", []),
            "acceptance_refs": ticket.get("acceptance_refs", []),
        },
        "reading_order": heading_section(str(ticket.get("_body", "")), "Leitura em ordem"),
        "decisions": heading_section(str(ticket.get("_body", "")), "Decisões já resolvidas"),
        "contract": heading_section(str(ticket.get("_body", "")), "Contrato técnico"),
        "examples": heading_section(str(ticket.get("_body", "")), "Exemplos de aceite"),
        "sequence": heading_section(str(ticket.get("_body", "")), "Sequência de execução"),
        "validation": heading_section(str(ticket.get("_body", "")), "Validação"),
        "return_condition": heading_section(str(ticket.get("_body", "")), "Condição de retorno"),
        "report": heading_section(str(ticket.get("_body", "")), "Relatório de saída"),
        "sources": [
            source
            for source in (
                rel_path(ticket["_path"], project),
                rel_path(directory / "spec.md", project)
                if (directory / "spec.md").exists()
                else rel_path(directory / "change.md", project),
                rel_path(directory / "plan.md", project) if (directory / "plan.md").exists() else None,
            )
            if source
        ],
        "errors": errors,
        "warnings": validation.get("warnings", []),
        "dependencies": dependency_states,
        "blockers": blockers,
        "changed_inputs": changed_inputs,
        "untracked_inputs": untracked_inputs,
        "ready": not errors and not blockers and not changed_inputs and not untracked_inputs and ticket.get("status") == "ready",
        "return_to_planner_when": "Contrato incompatível, referência desatualizada, decisão nova ou recurso indisponível.",
    }
    if args.write:
        packet_path = project / ".hybrid" / "packets" / directory.name / f"{args.ticket}.md"
        packet_lines = [
            f"# Execution package: {args.ticket}",
            "",
            f"Source ticket: `{rel_path(ticket['_path'], project)}`",
            "",
            str(ticket.get("_body", "")).rstrip(),
            "",
            "## Generated readiness",
            "",
            f"- Ready: `{str(package['ready']).lower()}`",
            f"- Errors: {'; '.join(errors) if errors else 'none'}",
            f"- Warnings: {'; '.join(validation.get('warnings', [])) if validation.get('warnings') else 'none'}",
            f"- Blockers: {', '.join(blockers) if blockers else 'none'}",
            "",
        ]
        guarded_generated_write(project, packet_path, "\n".join(packet_lines), args.force)
        package["written"] = rel_path(packet_path, project)
    return {"outcome": "completed" if package["ready"] else "failed", "package": package}


def detect_skill_root(project: Path) -> Path:
    for candidate in (Path(".agents") / "skills", Path(".cursor") / "skills", Path(".github") / "skills"):
        if (project / candidate).is_dir():
            return project / candidate
    return project / Path(".agents") / "skills"


def copy_with_conflict(source: Path, target: Path, conflicts: list[str], changed: list[str], force: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256_file(source) == sha256_file(target):
            return
        if not force:
            conflicts.append(str(target))
            return
    shutil.copy2(source, target)
    changed.append(str(target))


def run_install(args: argparse.Namespace) -> dict[str, Any]:
    project = project_from(args.project)
    skill_root = Path(args.skill_root) if args.skill_root else detect_skill_root(project)
    if skill_root.is_absolute():
        skill_root = skill_root.resolve()
        try:
            skill_root.relative_to(project.resolve())
        except ValueError as exc:
            raise HybridError("skill_root must stay inside the project", "unsafe_path") from exc
    else:
        skill_root = safe_project_path(project, skill_root)
    if skill_root == project.resolve():
        raise HybridError("skill_root must be a directory below the project root", "unsafe_path")
    source_skills = PACKAGE_ROOT / "skills"
    source_shared = PACKAGE_ROOT / "shared"
    if not source_skills.is_dir() or not source_shared.is_dir():
        raise HybridError("The package must contain skills/ and shared/ before installation", "package_invalid")
    conflicts: list[str] = []
    changed: list[str] = []
    for source in sorted(source_skills.glob("hybrid-*/SKILL.md")):
        target = skill_root / source.parent.name / source.name
        copy_with_conflict(source, target, conflicts, changed, args.force)
    for source in sorted(source_shared.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(source_shared)
        copy_with_conflict(source, skill_root.parent / "shared" / relative, conflicts, changed, args.force)
        copy_with_conflict(source, project / ".hybrid" / "shared" / relative, conflicts, changed, args.force)
    copy_with_conflict(SCRIPT_PATH, project / ".hybrid" / "hybrid.py", conflicts, changed, args.force)
    manifest = {
        "schema_version": "1.0",
        "source": str(PACKAGE_ROOT),
        "skill_root": rel_path(skill_root, project),
        "files": sorted(rel_path(Path(path), project) for path in changed if Path(path).is_absolute()),
        "conflicts": [rel_path(Path(path), project) for path in conflicts if Path(path).is_absolute()],
        "timestamp": now_iso(),
    }
    project.joinpath(".hybrid").mkdir(parents=True, exist_ok=True)
    write_json(project / ".hybrid" / "install-manifest.json", manifest)
    result = {
        "outcome": "completed" if not conflicts else "failed",
        "project": str(project),
        "skill_root": rel_path(skill_root, project),
        "shared_root": rel_path(skill_root.parent / "shared", project),
        "runtime": ".hybrid/hybrid.py",
        "changed": manifest["files"],
        "conflicts": manifest["conflicts"],
        "next_action": "Review conflicts and rerun with an explicit resolution" if conflicts else "Run python .hybrid/hybrid.py init and invoke the installed hybrid-* skills",
    }
    if conflicts:
        raise HybridError(json.dumps(result, ensure_ascii=False), "install_conflict")
    return result


def run_validate_package(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = {
        "hybrid-start",
        "hybrid-discover",
        "hybrid-domain",
        "hybrid-specify",
        "hybrid-plan",
        "hybrid-slice",
        "hybrid-check",
        "hybrid-implement",
        "hybrid-verify",
        "hybrid-review",
    }
    skill_roots = [PACKAGE_ROOT / "skills"]
    installed_project = PACKAGE_ROOT.parent
    for candidate in (installed_project / ".agents" / "skills", installed_project / ".cursor" / "skills", installed_project / ".github" / "skills"):
        if candidate not in skill_roots:
            skill_roots.append(candidate)
    skill_root = next((candidate for candidate in skill_roots if candidate.is_dir()), skill_roots[0])
    found = {path.parent.name for path in skill_root.glob("hybrid-*/SKILL.md")}
    missing = sorted(expected - found)
    extra = sorted(found - expected)
    errors.extend(f"missing skill: {name}" for name in missing)
    warnings.extend(f"unlisted skill: {name}" for name in extra)
    for name in sorted(found):
        path = skill_root / name / "SKILL.md"
        try:
            metadata, _body, has_frontmatter = read_markdown(path)
        except HybridError as exc:
            errors.append(str(exc))
            continue
        if not has_frontmatter:
            errors.append(f"{rel_path(path, PACKAGE_ROOT)}: frontmatter is required")
        if metadata.get("name") != name:
            errors.append(f"{rel_path(path, PACKAGE_ROOT)}: name must match directory")
        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip() or len(description) > 1024:
            errors.append(f"{rel_path(path, PACKAGE_ROOT)}: description must be non-empty and <=1024 characters")
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            errors.append(f"{rel_path(path, PACKAGE_ROOT)}: SKILL.md has {line_count} lines; keep it under 500")
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = link.strip().split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "<")):
                continue
            target_path = (path.parent / target).resolve()
            if not target_path.exists():
                errors.append(f"{rel_path(path, PACKAGE_ROOT)}: unresolved reference {target}")
    for schema in sorted((SHARED_ROOT / "schemas").glob("*.json")):
        try:
            value = json.loads(schema.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or "$schema" not in value or "$id" not in value:
                errors.append(f"{rel_path(schema, PACKAGE_ROOT)}: invalid schema envelope")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{rel_path(schema, PACKAGE_ROOT)}: {exc}")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    try:
        compile(script_text, str(SCRIPT_PATH), "exec")
    except SyntaxError as exc:
        errors.append(f"scripts/hybrid.py: {exc}")
    return {
        "outcome": "completed" if not errors else "failed",
        "ok": not errors,
        "package": str(PACKAGE_ROOT),
        "skills": sorted(found),
        "skill_count": len(found),
        "schema_count": len(list((SHARED_ROOT / "schemas").glob("*.json"))),
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hybrid", description="Local deterministic runtime for hybrid development skills")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create project-local hybrid configuration")
    init.add_argument("--project", default=".")
    init.add_argument("--mode", choices=["standard", "compact", "expanded"])
    init.add_argument("--json", action="store_true")

    scaffold = sub.add_parser("scaffold", help="Create a standard or compact effort")
    add_paths_argument(scaffold)
    scaffold.add_argument("--mode", choices=["standard", "compact", "expanded"])
    scaffold.add_argument("--title")
    scaffold.add_argument("--force", action="store_true")

    next_id = sub.add_parser("next-id", help="Calculate the next stable ID without editing files")
    add_paths_argument(next_id)
    next_id.add_argument("--prefix", required=True, choices=["TK", "FR", "AC", "EV", "FD"])

    validate = sub.add_parser("validate", help="Validate config and hybrid artifacts")
    validate.add_argument("--project", default=".")
    validate.add_argument("--effort")
    validate.add_argument("--require-config", action="store_true")
    validate.add_argument("--json", action="store_true")

    graph = sub.add_parser("graph", help="Validate and inspect ticket dependencies")
    add_paths_argument(graph)

    render = sub.add_parser("render", help="Generate todo/backlog projections")
    render.add_argument("--project", default=".")
    render.add_argument("--effort")
    render.add_argument("--view", choices=["todo", "backlog", "all"], default="all")
    render.add_argument("--force", action="store_true")
    render.add_argument("--json", action="store_true")

    start = sub.add_parser("start", help="Inspect context, baseline, state, and changed inputs")
    start.add_argument("--project", default=".")
    start.add_argument("--effort")
    start.add_argument("--json", action="store_true")

    checkpoint = sub.add_parser("checkpoint", help="Write an atomic optimistic checkpoint")
    checkpoint_sub = checkpoint.add_subparsers(dest="checkpoint_command", required=False)
    checkpoint_write = checkpoint_sub.add_parser("write", help="Write checkpoint")
    add_paths_argument(checkpoint_write)
    checkpoint_write.add_argument("--expected-revision", type=int)
    checkpoint_write.add_argument("--phase")
    checkpoint_write.add_argument("--status")
    checkpoint_write.add_argument("--next-action")
    checkpoint_write.add_argument("--active-ticket")
    checkpoint_write.add_argument("--last-evidence")
    checkpoint_write.add_argument("--pending-question", action="append")
    checkpoint_write.add_argument("--blocker", action="append")
    checkpoint_write.add_argument("--input", action="append", help="Register an input as name=path; repeat as needed")
    checkpoint_write.set_defaults(checkpoint_command="write")

    invalidate = sub.add_parser("invalidate", help="Find and optionally mark stale evidence")
    add_paths_argument(invalidate)
    invalidate.add_argument("--write", action="store_true")

    evidence = sub.add_parser("evidence", help="Manage evidence records")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_add = evidence_sub.add_parser("add")
    add_paths_argument(evidence_add)
    evidence_add.add_argument("--ticket", help="Ticket ID; omit only for compact change evidence")
    evidence_add.add_argument("--acceptance-refs", required=True, help="Comma-separated AC IDs")
    evidence_add.add_argument("--procedure", required=True)
    evidence_add.add_argument("--result", choices=sorted(EVIDENCE_RESULTS), required=True)
    evidence_add.add_argument("--executed", action="store_true", help="Assert that the procedure really ran")
    evidence_add.add_argument("--path", action="append", help="Input path; repeat as needed")
    evidence_add.add_argument("--paths", nargs="+", help="Input paths")
    evidence_add.add_argument("--environment")
    evidence_add.add_argument("--observations")
    evidence_add.add_argument("--evidence-ref", action="append")
    evidence_add.add_argument("--limitations")
    evidence_add.add_argument("--force", action="store_true")
    evidence_add.set_defaults(evidence_command="add")

    ticket = sub.add_parser("ticket", help="Update ticket state without changing its contract")
    ticket_sub = ticket.add_subparsers(dest="ticket_command", required=True)
    ticket_update = ticket_sub.add_parser("update")
    add_paths_argument(ticket_update)
    ticket_update.add_argument("--ticket", required=True)
    ticket_update.add_argument("--status", choices=sorted(TICKET_STATUSES))
    ticket_update.add_argument("--verification-status", choices=sorted(VERIFICATION_STATUSES))
    ticket_update.add_argument("--note")
    ticket_update.set_defaults(ticket_command="update")

    finding = sub.add_parser("finding", help="Manage convergence/review findings")
    finding_sub = finding.add_subparsers(dest="finding_command", required=True)
    finding_add = finding_sub.add_parser("add")
    add_paths_argument(finding_add)
    finding_add.add_argument("--origin", choices=["consistency", "standards", "spec", "convergence"], required=True)
    finding_add.add_argument("--source-ref")
    finding_add.add_argument("--gap-type", required=True)
    finding_add.add_argument("--area", required=True)
    finding_add.add_argument("--severity", choices=["blocker", "major", "minor", "note"], required=True)
    finding_add.add_argument("--summary", required=True)
    finding_add.add_argument("--evidence-location")
    finding_add.add_argument("--consequence")
    finding_add.add_argument("--fix-ticket")
    finding_add.add_argument("--discriminator")
    finding_add.set_defaults(finding_command="add")

    dedupe = sub.add_parser("dedupe", help="Deduplicate open findings by their stable key")
    add_paths_argument(dedupe)
    dedupe.add_argument("--write", action="store_true")

    check = sub.add_parser("check", help="Analyze consistency or convergence without changing the contract")
    add_paths_argument(check)
    check.add_argument("--mode", choices=["consistency", "convergence"], default="consistency")
    check.add_argument("--write", action="store_true", help="Persist findings; never changes spec acceptance")
    check.add_argument("--area")

    package = sub.add_parser("package", help="Check and emit the execution package for one ticket")
    add_paths_argument(package)
    package.add_argument("--ticket", required=True)
    package.add_argument("--write", action="store_true")
    package.add_argument("--force", action="store_true")

    install = sub.add_parser("install", help="Install skills and local shared resources into a project")
    install.add_argument("--project", default=".")
    install.add_argument("--skill-root", help="Destination such as .agents/skills")
    install.add_argument("--force", action="store_true")
    install.add_argument("--json", action="store_true")

    package_validate = sub.add_parser("package-validate", aliases=["validate-package"], help="Validate this skills package")
    package_validate.add_argument("--json", action="store_true")

    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "init":
        return run_init(args)
    if command == "scaffold":
        return run_scaffold(args)
    if command == "next-id":
        return run_next_id(args)
    if command == "validate":
        return run_validate(args)
    if command == "graph":
        return run_graph(args)
    if command == "render":
        return run_render(args)
    if command == "start":
        return run_start(args)
    if command == "checkpoint":
        if getattr(args, "checkpoint_command", None) in {None, "write"}:
            return run_checkpoint(args)
    if command == "invalidate":
        return run_invalidate(args)
    if command == "evidence" and args.evidence_command == "add":
        return run_evidence_add(args)
    if command == "ticket" and args.ticket_command == "update":
        return run_ticket_update(args)
    if command == "finding" and args.finding_command == "add":
        return run_finding_add(args)
    if command == "dedupe":
        return run_dedupe(args)
    if command == "check":
        return run_check(args)
    if command == "package":
        return run_package(args)
    if command == "install":
        return run_install(args)
    if command in {"package-validate", "validate-package"}:
        return run_validate_package(args)
    raise HybridError("Unknown command", "command")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
    except HybridError as exc:
        payload: dict[str, Any] = {"outcome": "blocked" if exc.code in {"checkpoint_conflict", "write_conflict", "install_conflict"} else "failed", "error": exc.code, "message": str(exc)}
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR [{exc.code}]: {exc}", file=sys.stderr)
        return 2
    as_json = bool(getattr(args, "json", False))
    emit(result, as_json)
    return 0 if result.get("outcome") in {"completed"} and result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
