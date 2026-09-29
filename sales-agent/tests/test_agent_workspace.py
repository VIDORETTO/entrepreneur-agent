import argparse
import json
import re
from pathlib import Path

import pytest

from sales_agent.cli import build_parser, main
from sales_agent.skills import SkillCatalog

ADAPTATION_SKILLS = {
    "seller-adapt",
    "seller-tune-conversation",
    "seller-evaluate-and-tune",
    "seller-connect-channel",
    "seller-pilot-readiness",
    "seller-extend-runtime",
}
REPOSITORY = Path(__file__).resolve().parents[1]
BEGIN = "<!-- vendedor-adaptavel:begin"
END = "<!-- vendedor-adaptavel:end -->"


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip().startswith("{") else out


def test_install_codex_writes_agents_md_skills_and_registry_only(tmp_path, capsys):
    code, report = run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    assert code == 0
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert BEGIN in agents and END in agents
    assert (tmp_path / ".agents/skills/seller-adapt/SKILL.md").is_file()
    assert (tmp_path / ".vendedor-workspace.json").is_file()
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "CLAUDE.md").exists()
    assert ".agents/skills/seller-adapt/SKILL.md" in report["written"]


def test_install_claude_writes_claude_md_importing_agents_md(tmp_path, capsys):
    code, _ = run(capsys, "skills", "install", "--target", "claude", "--dir", str(tmp_path))
    assert code == 0
    assert (tmp_path / ".claude/skills/seller-adapt/SKILL.md").is_file()
    assert "@AGENTS.md" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert (tmp_path / "AGENTS.md").is_file()
    assert not (tmp_path / ".agents").exists()


def test_install_preserves_user_agents_md_and_never_duplicates_block(tmp_path, capsys):
    original = "# Meu projeto\n\nRegra minha: nunca prometer prazo.\n"
    (tmp_path / "AGENTS.md").write_text(original, encoding="utf-8")
    run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    first = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert first.startswith(original)
    assert first.count(BEGIN) == 1

    (tmp_path / "AGENTS.md").write_text(first + "\n## Notas do time\nUsar tom formal.\n", encoding="utf-8")
    run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    second = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert second.count(BEGIN) == 1
    assert second.startswith(original)
    assert second.endswith("## Notas do time\nUsar tom formal.\n")


def test_modified_skill_is_kept_unless_forced(tmp_path, capsys):
    run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    skill = tmp_path / ".agents/skills/seller-adapt/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nAjuste local.\n", encoding="utf-8")

    code, report = run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    assert code == 0
    assert "Ajuste local." in skill.read_text(encoding="utf-8")
    skipped = {item["path"]: item["reason"] for item in report["skipped"]}
    assert skipped[".agents/skills/seller-adapt/SKILL.md"] == "modified"

    code, report = run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path), "--force")
    assert "Ajuste local." not in skill.read_text(encoding="utf-8")
    assert ".agents/skills/seller-adapt/SKILL.md" in report["written"]


def test_unregistered_different_file_is_not_overwritten(tmp_path, capsys):
    target = tmp_path / ".agents/skills/seller-adapt/SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("skill do usuário\n", encoding="utf-8")
    _, report = run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    assert target.read_text(encoding="utf-8") == "skill do usuário\n"
    assert {"path": ".agents/skills/seller-adapt/SKILL.md", "reason": "unregistered_conflict"} in report["skipped"]


def test_reinstall_is_idempotent_and_dry_run_writes_nothing(tmp_path, capsys):
    _, plan = run(capsys, "skills", "install", "--target", "all", "--dir", str(tmp_path / "vazio"), "--dry-run")
    assert plan["dry_run"] is True and plan["written"]
    assert not (tmp_path / "vazio").exists() or not any((tmp_path / "vazio").iterdir())

    run(capsys, "skills", "install", "--target", "all", "--dir", str(tmp_path))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    _, report = run(capsys, "skills", "install", "--target", "all", "--dir", str(tmp_path))
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert report["written"] == [] and report["skipped"] == []
    assert before == after


def test_unknown_target_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["skills", "install", "--target", "vscode", "--dir", str(tmp_path)])
    assert error.value.code == 2


def test_adaptation_skills_are_cataloged_but_never_selected_for_buyer_context():
    runtime = SkillCatalog()
    assert not ADAPTATION_SKILLS & {item["id"] for item in runtime.list_skills()}
    assert runtime.read_skill("seller-adapt")["available"] is False
    catalog = SkillCatalog(include_adaptation=True)
    listed = {item["id"]: item for item in catalog.list_skills()}
    assert ADAPTATION_SKILLS <= set(listed)
    assert all(listed[skill]["audience"] == "developer-adaptation" for skill in ADAPTATION_SKILLS)
    assert catalog.diagnose()["ok"] is True
    package = {"skills": [{"id": skill, "version": "1", "when": "always"} for skill in ADAPTATION_SKILLS]}
    for candidate in (runtime, catalog):
        selected = candidate.select(package, "quero comprar", {})
        assert selected["selected"] == [] and selected["applied"] == []


def test_init_installs_agent_files_only_when_requested(tmp_path, capsys):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert main(["--data-dir", str(tmp_path / "d1"), "init", "--workspace", str(workspace)]) == 0
    capsys.readouterr()
    assert list(workspace.iterdir()) == []

    assert main(["--data-dir", str(tmp_path / "d2"), "init", "--agents", "codex", "--workspace", str(workspace)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert (tmp_path / "d2").is_dir()
    assert (workspace / "AGENTS.md").is_file()
    assert (workspace / ".agents/skills/seller-adapt/SKILL.md").is_file()
    assert result["agent_files"]["written"]


def test_status_reports_modified_missing_and_outdated(tmp_path, capsys):
    run(capsys, "skills", "install", "--target", "codex", "--dir", str(tmp_path))
    _, clean = run(capsys, "skills", "status", "--dir", str(tmp_path))
    assert clean["ok"] is True and clean["outdated"] is False

    edited = tmp_path / ".agents/skills/seller-adapt/SKILL.md"
    edited.write_text("mudou\n", encoding="utf-8")
    (tmp_path / ".agents/skills/seller-connect-channel/SKILL.md").unlink()
    registry_path = tmp_path / ".vendedor-workspace.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["package_version"] = "0.0.0"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    _, status = run(capsys, "skills", "status", "--dir", str(tmp_path))
    states = {item["path"]: item["state"] for item in status["files"]}
    assert states[".agents/skills/seller-adapt/SKILL.md"] == "modified"
    assert states[".agents/skills/seller-connect-channel/SKILL.md"] == "missing"
    assert status["outdated"] is True and status["ok"] is False


def test_status_without_installation_says_so(tmp_path, capsys):
    code, status = run(capsys, "skills", "status", "--dir", str(tmp_path))
    assert code == 0 and status["installed"] is False


def _subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def _shipped_texts():
    paths = [REPOSITORY / "src/sales_agent/resources/workspace/AGENTS.md"]
    paths += sorted((REPOSITORY / "skills").glob("*/SKILL.md"))
    return [(path, path.read_text(encoding="utf-8")) for path in paths]


def _command_candidates(text):
    """Code spans that start with the CLI name; comments and continuations removed."""

    joined = re.sub(r"\\\n\s*", " ", text)
    candidates = []
    for block in re.findall(r"```[^\n]*\n(.*?)```", joined, re.DOTALL):
        candidates += [line.split(" #")[0].strip() for line in block.splitlines()]
    candidates += re.findall(r"`([^`\n]+)`", re.sub(r"```.*?```", "", joined, flags=re.DOTALL))
    return [item for item in candidates if item.startswith("vendedor ")]


def test_cited_commands_flags_and_package_keys_exist():
    root = build_parser()
    schema = json.loads((REPOSITORY / "schemas/business-package.schema.json").read_text(encoding="utf-8"))
    errors = []
    checked = 0
    for path, text in _shipped_texts():
        for command in _command_candidates(text):
            tokens = command.split()[1:]
            index = 0
            while index < len(tokens) and tokens[index] == "--data-dir":
                index += 2
            if index >= len(tokens):
                continue
            choices = _subparsers(root)
            name = tokens[index]
            if name not in choices:
                errors.append("%s: comando desconhecido `%s`" % (path.name, command))
                continue
            checked += 1
            parser = choices[name]
            index += 1
            nested = _subparsers(parser)
            if nested and index < len(tokens) and not tokens[index].startswith(("-", "<")):
                if tokens[index] not in nested:
                    errors.append("%s: subcomando desconhecido `%s`" % (path.name, command))
                    continue
                parser = nested[tokens[index]]
                index += 1
            known = {opt for action in parser._actions for opt in action.option_strings}
            for token in tokens[index:]:
                if token.startswith("--") and token.split("=")[0] not in known:
                    errors.append("%s: opção desconhecida %s em `%s`" % (path.name, token, command))
        for key in re.findall(r"package\.([a-z_]+)", text):
            if key not in schema["properties"] and key not in {"settings", "json"}:
                errors.append("%s: chave de pacote desconhecida package.%s" % (path.name, key))
        assert not re.search(r"sk-[A-Za-z0-9]{10,}|\b\d{11}\b|@[a-z0-9-]+\.(com|br)\b", text), path.name
    assert checked >= 20
    assert errors == []


def test_shipped_template_and_skills_exist_in_wheel_configuration():
    config = (REPOSITORY / "pyproject.toml").read_text(encoding="utf-8")
    assert "resources/workspace/*.md" in config
    for skill in ADAPTATION_SKILLS:
        assert '"share/vendedor-adaptavel/skills/%s"' % skill in config


def test_package_cannot_declare_an_adaptation_skill_for_the_buyer(app):
    from sales_agent.validation import PackageError, validate_package

    store, _ = app
    package = store.get_business("azul-b2c")
    package["skills"] = [{"id": "seller-adapt", "version": "1", "when": "always"}]
    with pytest.raises(PackageError, match="skill desconhecida"):
        validate_package(package)
