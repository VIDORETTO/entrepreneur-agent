"""Command-line harness for installation, configuration, demo and evaluation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .config import ConfigurationManager, load_manifest, load_package, promote_package, seed_examples, seed_package
from .conversation import ConversationError, SellerEngine
from .evaluation import EvaluationRunner
from .knowledge import FarolArtifactImporter, PersistentFarolKnowledge
from .model import HTTPModelAdapter, RuleBasedModel
from .storage import StateStore
from .validation import PackageError, validate_package


def _store(args: argparse.Namespace) -> StateStore:
    return StateStore(Path(args.data_dir))


def _print(value: Any, pretty: bool = True) -> None:
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty))


def command_doctor(args: argparse.Namespace) -> int:
    store = _store(args)
    storage_report = store.integrity_report()
    diagnostics: Dict[str, Any] = {
        "ok": storage_report["ok"],
        "python": sys.version.split()[0],
        "python_supported": sys.version_info >= (3, 9),
        "sqlite": __import__("sqlite3").sqlite_version,
        "data_dir": str(store.data_dir),
        "data_dir_writable": os.access(str(store.data_dir), os.W_OK),
        "businesses": [item["business"]["id"] for item in store.list_businesses()],
        "model": {"adapter": "rules-v1", "configured_remote": bool(os.environ.get("SELLER_MODEL_URL"))},
        "farol": {
            "command_available": bool(shutil.which("farol") or shutil.which("docops")),
            "upstream_rag_validated": False,
            "reason": "a instalação upstream opcional do Farol não foi executada nesta instalação",
        },
        "dependencies": {"external_runtime": "none", "pytest": importlib.util.find_spec("pytest") is not None},
        "storage": storage_report,
    }
    try:
        manifest = load_manifest()
        diagnostics["manifest"] = {"version": manifest.get("version"), "sources": len(manifest.get("sources", []))}
        diagnostics["sales_skills_excluded"] = any(
            item.get("name") == "Sales-Skills" for item in manifest.get("excluded_sources", [])
        )
    except (OSError, ValueError) as exc:
        diagnostics["ok"] = False
        diagnostics["manifest_error"] = str(exc)
    if not diagnostics["python_supported"] or not diagnostics["data_dir_writable"]:
        diagnostics["ok"] = False
    _print(diagnostics, pretty=not args.quiet)
    return 0 if diagnostics["ok"] else 2


def command_init(args: argparse.Namespace) -> int:
    store = _store(args)
    result: Dict[str, Any] = {"data_dir": str(store.data_dir), "initialized": True}
    if args.examples:
        result["businesses"] = [item["business"]["id"] for item in seed_examples(store)]
    _print(result)
    return 0


def command_examples(args: argparse.Namespace) -> int:
    store = _store(args)
    packages = seed_examples(store)
    _print({"businesses": [item["business"]["id"] for item in packages], "count": len(packages)})
    return 0


def command_validate(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.package:
        package = load_package(args.package)
        _print({"valid": True, "business_id": package["business"]["id"]})
        return 0
    values = []
    for package in store.list_businesses():
        try:
            validate_package(package)
            values.append({"business_id": package["business"]["id"], "valid": True})
        except PackageError as exc:
            values.append({"business_id": package.get("business", {}).get("id"), "valid": False, "error": str(exc)})
    valid = bool(values) and all(item["valid"] for item in values)
    payload: Dict[str, Any] = {"valid": valid, "packages": values}
    if not values:
        payload["error"] = "nenhum negócio instalado; use 'vendedor examples' ou 'vendedor import-package'"
    _print(payload)
    return 0 if valid else 2


def command_import_package(args: argparse.Namespace) -> int:
    store = _store(args)
    package = load_package(args.package)
    seed_package(store, package)
    _print({"imported": package["business"]["id"], "sources": len(package.get("sources", []))})
    return 0


def command_export_package(args: argparse.Namespace) -> int:
    package = _store(args).get_business(args.business_id)
    if not package:
        raise ValueError("negócio não configurado: %s" % args.business_id)
    if args.output:
        output = Path(args.output)
        output.write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _print({"exported": args.business_id, "output": str(output)})
    else:
        _print(package)
    return 0


def command_promote_package(args: argparse.Namespace) -> int:
    store = _store(args)
    package = promote_package(store, load_package(args.package))
    version = store.list_business_versions(package["business"]["id"])[-1]["version"]
    _print(
        {
            "promoted": package["business"]["id"],
            "package_version": package["package_version"],
            "storage_version": version,
            "lifecycle": package["lifecycle"],
        }
    )
    return 0


def command_configure_start(args: argparse.Namespace) -> int:
    store = _store(args)
    materials = []
    total_size = 0
    for path in args.material or []:
        material_path = Path(path)
        size = material_path.stat().st_size
        total_size += size
        if size > 5_000_000 or total_size > 10_000_000:
            raise ValueError("materiais excedem o limite seguro de tamanho")
        materials.append(material_path.read_text(encoding="utf-8"))
    manager = ConfigurationManager(store)
    payload = manager.start(
        args.business_id,
        template=args.template,
        business_name=args.business_name,
        materials=materials,
        session_id=args.session_id,
    )
    _print(_discovery_view(payload))
    return 0


def command_configure_status(args: argparse.Namespace) -> int:
    payload = ConfigurationManager(_store(args)).status(args.session_id)
    _print(_discovery_view(payload))
    return 0


def command_configure_answer(args: argparse.Namespace) -> int:
    payload = ConfigurationManager(_store(args)).answer(args.session_id, args.answer, question_id=args.question_id)
    _print(_discovery_view(payload))
    return 0


def command_configure_finalize(args: argparse.Namespace) -> int:
    store = _store(args)
    package = ConfigurationManager(store).finalize(args.session_id)
    version = store.list_business_versions(package["business"]["id"])[-1]["version"]
    _print({"finalized": True, "business_id": package["business"]["id"], "version": version})
    return 0


def _discovery_view(payload: Dict[str, Any]) -> Dict[str, Any]:
    index = int(payload.get("next_question_index", 0))
    questions = payload.get("questions", [])
    next_question = questions[index] if index < len(questions) else None
    return {
        "session_id": payload.get("session_id"),
        "business_id": payload.get("business_id"),
        "status": payload.get("status"),
        "document_findings": payload.get("document_findings", []),
        "confirmed_decisions": payload.get("decisions", []),
        "answered_question_ids": payload.get("answered_question_ids", []),
        "pending_decision_ids": payload.get("deferred_question_ids", []),
        "next_question": next_question,
        "capabilities": payload.get("capabilities", {}),
    }


def _engine_for(store: StateStore, args: argparse.Namespace) -> SellerEngine:
    model = RuleBasedModel()
    endpoint = os.environ.get("SELLER_MODEL_URL")
    key = os.environ.get("SELLER_MODEL_API_KEY")
    model_name = os.environ.get("SELLER_MODEL_NAME", "configured-model")
    if endpoint and key and not getattr(args, "rules", False):
        model = HTTPModelAdapter(endpoint, key, model_name)  # type: ignore[assignment]
    return SellerEngine(store, model=model)


def command_chat(args: argparse.Namespace) -> int:
    store = _store(args)
    engine = _engine_for(store, args)
    event = {
        "business_id": args.business_id,
        "conversation_id": args.conversation_id,
        "contact_id": args.contact_id,
        "channel": args.channel,
        "event_id": args.event_id,
        "text": args.message,
    }
    result = engine.handle(event)
    if args.json:
        _print(result.as_dict())
    else:
        print(result.response)
        if result.action:
            print("[ação] " + json.dumps(result.action, ensure_ascii=False, sort_keys=True))
    return 0


def command_knowledge_query(args: argparse.Namespace) -> int:
    store = _store(args)
    hits = PersistentFarolKnowledge(store).search(args.business_id, args.query, args.max_results)
    _print({"backend": PersistentFarolKnowledge(store).metadata(), "hits": hits})
    return 0


def command_knowledge_revoke(args: argparse.Namespace) -> int:
    store = _store(args)
    count = PersistentFarolKnowledge(store).revoke(args.business_id, args.source_id, args.version)
    _print({"revoked": count, "business_id": args.business_id, "source_id": args.source_id})
    return 0


def command_farol_import(args: argparse.Namespace) -> int:
    store = _store(args)
    count = FarolArtifactImporter(PersistentFarolKnowledge(store)).import_package(args.business_id, args.path)
    _print({"imported_documents": count, "backend": "farol-artifact-v1", "business_id": args.business_id})
    return 0


def command_demo(args: argparse.Namespace) -> int:
    if args.persist:
        return _run_demo(StateStore(Path(args.data_dir)))
    with tempfile.TemporaryDirectory(prefix="vendedor-demo-") as temporary:
        return _run_demo(StateStore(Path(temporary)))


def _run_demo(store: StateStore) -> int:
    seed_examples(store)
    engine = SellerEngine(store)
    runs = [
        (
            "azul-b2c",
            "demo-physical",
            "verified:alice",
            ["Quero comprar a camiseta azul tamanho M, 1 unidade para SP."],
        ),
        (
            "nuvem-b2b",
            "demo-b2b",
            "verified:empresa",
            ["Preciso de 5 licenças do plano padrão para a empresa Nuvem Clara, empresa Nuvem Clara, contato compras@nuvem.test."],
        ),
        (
            "reforma-consultiva",
            "demo-service",
            "verified:bruna",
            ["Quero reformar minha cozinha. Quanto sai?", "Reforma completa em SP; quero preparar o orçamento."],
        ),
        (
            "curso-digital",
            "demo-digital",
            "verified:diego",
            ["Quero comprar o curso de análise, meu e-mail é diego@exemplo.test."],
        ),
    ]
    output = []
    for business_id, conversation_id, contact_id, messages in runs:
        for index, message in enumerate(messages, start=1):
            result = engine.handle(
                {
                    "business_id": business_id,
                    "conversation_id": conversation_id,
                    "contact_id": contact_id,
                    "channel": "cli-demo",
                    "event_id": "%s-%02d" % (conversation_id, index),
                    "text": message,
                }
            )
            output.append(
                {
                    "business_id": business_id,
                    "message": message,
                    "response": result.response,
                    "action": result.action,
                    "state": {"phase": result.state.get("phase"), "operation": result.state.get("operation")},
                }
            )
    _print({"mode": "fictional-demo", "runs": output})
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    runner = EvaluationRunner(Path(args.data_dir))
    report = runner.run()
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print(report)
    return 0 if report["summary"]["critical_failures"] == 0 and report["summary"]["failed"] == 0 else 2


def command_model_check(args: argparse.Namespace) -> int:
    from .evaluation import model_contract_check

    _print(model_contract_check())
    return 0


def command_storage_check(args: argparse.Namespace) -> int:
    report = _store(args).integrity_report()
    _print(report)
    return 0 if report["ok"] else 2


def command_storage_backup(args: argparse.Namespace) -> int:
    output = _store(args).backup_to(args.output)
    _print({"backup": str(output), "created": True})
    return 0


def command_storage_restore(args: argparse.Namespace) -> int:
    result = _store(args).restore_from(args.input, args.backup_current)
    _print(result)
    return 0


def command_outbox_list(args: argparse.Namespace) -> int:
    items = _store(args).list_outbox(args.status)
    _print({"items": items, "count": len(items)})
    return 0


def command_outbox_claim(args: argparse.Namespace) -> int:
    items = _store(args).claim_outbox(args.limit, args.lease_seconds)
    _print({"items": items, "count": len(items)})
    return 0


def command_outbox_ack(args: argparse.Namespace) -> int:
    acknowledged = _store(args).ack_outbox(args.message_key)
    if not acknowledged:
        raise ValueError("mensagem não está em processamento: %s" % args.message_key)
    _print({"message_key": args.message_key, "status": "sent"})
    return 0


def command_outbox_nack(args: argparse.Namespace) -> int:
    status = _store(args).nack_outbox(
        args.message_key,
        args.error,
        max_attempts=args.max_attempts,
        delay_seconds=args.delay_seconds,
    )
    _print({"message_key": args.message_key, "status": status})
    return 0


def command_outbox_recover(args: argparse.Namespace) -> int:
    count = _store(args).recover_expired_outbox()
    _print({"recovered": count})
    return 0


def command_effects_list(args: argparse.Namespace) -> int:
    items = _store(args).list_effects(args.status)
    _print({"items": items, "count": len(items)})
    return 0


def command_effects_reconcile(args: argparse.Namespace) -> int:
    details = json.loads(args.details) if args.details else {}
    if not isinstance(details, dict):
        raise ValueError("details precisa ser um objeto JSON")
    result = _store(args).reconcile_effect(args.effect_key, args.resolution, details)
    _print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vendedor", description="Vendedor Adaptável — runtime local demonstrável")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument("--data-dir", default=".vendedor-data", help="diretório privado de estado")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="diagnosticar instalação e capacidades")
    doctor.add_argument("--quiet", action="store_true")
    doctor.set_defaults(func=command_doctor)

    init = sub.add_parser("init", help="criar banco privado")
    init.add_argument("--examples", action="store_true")
    init.set_defaults(func=command_init)
    examples = sub.add_parser("examples", help="instalar os quatro negócios fictícios")
    examples.set_defaults(func=command_examples)

    validate = sub.add_parser("validate", help="validar pacote ou negócios instalados")
    validate.add_argument("--package")
    validate.set_defaults(func=command_validate)
    import_cmd = sub.add_parser("import-package", help="importar um package.json versionado")
    import_cmd.add_argument("package")
    import_cmd.set_defaults(func=command_import_package)
    export_cmd = sub.add_parser("export-package", help="exportar um pacote instalado para revisão")
    export_cmd.add_argument("--business-id", required=True)
    export_cmd.add_argument("--output")
    export_cmd.set_defaults(func=command_export_package)
    promote_cmd = sub.add_parser("promote-package", help="promover um rascunho revisado para active")
    promote_cmd.add_argument("package")
    promote_cmd.set_defaults(func=command_promote_package)

    configure = sub.add_parser("configure", help="entrevista persistente do dono")
    configure_sub = configure.add_subparsers(dest="configure_command", required=True)
    start = configure_sub.add_parser("start")
    start.add_argument("--business-id", required=True)
    start.add_argument("--business-name")
    start.add_argument("--template", choices=["physical", "b2b", "service", "digital"], default="physical")
    start.add_argument("--material", action="append")
    start.add_argument("--session-id")
    start.set_defaults(func=command_configure_start)
    status = configure_sub.add_parser("status")
    status.add_argument("session_id")
    status.set_defaults(func=command_configure_status)
    answer = configure_sub.add_parser("answer")
    answer.add_argument("session_id")
    answer.add_argument("answer")
    answer.add_argument("--question-id")
    answer.set_defaults(func=command_configure_answer)
    finalize = configure_sub.add_parser("finalize")
    finalize.add_argument("session_id")
    finalize.set_defaults(func=command_configure_finalize)

    chat = sub.add_parser("chat", help="processar uma mensagem persistente")
    chat.add_argument("--business-id", required=True)
    chat.add_argument("--conversation-id", required=True)
    chat.add_argument("--contact-id", required=True)
    chat.add_argument("--event-id", required=True)
    chat.add_argument("--message", required=True)
    chat.add_argument("--channel", default="cli")
    chat.add_argument("--json", action="store_true")
    chat.add_argument("--rules", action="store_true")
    chat.set_defaults(func=command_chat)

    knowledge = sub.add_parser("knowledge", help="consultar e governar evidências")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    query = knowledge_sub.add_parser("query")
    query.add_argument("--business-id", required=True)
    query.add_argument("query")
    query.add_argument("--max-results", type=int, default=5)
    query.set_defaults(func=command_knowledge_query)
    revoke = knowledge_sub.add_parser("revoke")
    revoke.add_argument("--business-id", required=True)
    revoke.add_argument("--source-id", required=True)
    revoke.add_argument("--version")
    revoke.set_defaults(func=command_knowledge_revoke)

    farol = sub.add_parser("farol", help="importar artefatos gerados pelo Farol")
    farol_sub = farol.add_subparsers(dest="farol_command", required=True)
    farol_import = farol_sub.add_parser("import")
    farol_import.add_argument("--business-id", required=True)
    farol_import.add_argument("path")
    farol_import.set_defaults(func=command_farol_import)

    demo = sub.add_parser("demo", help="executar as quatro demonstrações fictícias")
    demo.add_argument("--persist", action="store_true", help="manter o estado da demonstração em --data-dir")
    demo.set_defaults(func=command_demo)
    evaluate = sub.add_parser("evaluate", help="executar cenários AC e gerar relatório")
    evaluate.add_argument("--output")
    evaluate.set_defaults(func=command_evaluate)
    model_check = sub.add_parser("model-check", help="testar contrato do adaptador de modelo")
    model_check.set_defaults(func=command_model_check)

    storage = sub.add_parser("storage", help="verificar, copiar ou restaurar o estado SQLite")
    storage_sub = storage.add_subparsers(dest="storage_command", required=True)
    storage_check = storage_sub.add_parser("check", help="verificar integridade e versão")
    storage_check.set_defaults(func=command_storage_check)
    storage_backup = storage_sub.add_parser("backup", help="criar backup consistente sem sobrescrever arquivos")
    storage_backup.add_argument("output")
    storage_backup.set_defaults(func=command_storage_backup)
    storage_restore = storage_sub.add_parser("restore", help="restaurar backup após preservar o estado atual")
    storage_restore.add_argument("input")
    storage_restore.add_argument("--backup-current", required=True)
    storage_restore.set_defaults(func=command_storage_restore)

    outbox = sub.add_parser("outbox", help="operar entrega durável de mensagens")
    outbox_sub = outbox.add_subparsers(dest="outbox_command", required=True)
    outbox_list = outbox_sub.add_parser("list")
    outbox_list.add_argument("--status", choices=["pending", "processing", "sent", "cancelled", "dead_letter"])
    outbox_list.set_defaults(func=command_outbox_list)
    outbox_claim = outbox_sub.add_parser("claim")
    outbox_claim.add_argument("--limit", type=int, default=10)
    outbox_claim.add_argument("--lease-seconds", type=int, default=60)
    outbox_claim.set_defaults(func=command_outbox_claim)
    outbox_ack = outbox_sub.add_parser("ack")
    outbox_ack.add_argument("message_key")
    outbox_ack.set_defaults(func=command_outbox_ack)
    outbox_nack = outbox_sub.add_parser("nack")
    outbox_nack.add_argument("message_key")
    outbox_nack.add_argument("--error", required=True)
    outbox_nack.add_argument("--max-attempts", type=int, default=5)
    outbox_nack.add_argument("--delay-seconds", type=int, default=30)
    outbox_nack.set_defaults(func=command_outbox_nack)
    outbox_recover = outbox_sub.add_parser("recover")
    outbox_recover.set_defaults(func=command_outbox_recover)

    effects = sub.add_parser("effects", help="inspecionar e conciliar efeitos persistentes")
    effects_sub = effects.add_subparsers(dest="effects_command", required=True)
    effects_list = effects_sub.add_parser("list")
    effects_list.add_argument("--status", choices=["reserved", "unknown", "confirmed", "failed"])
    effects_list.set_defaults(func=command_effects_list)
    effects_reconcile = effects_sub.add_parser("reconcile")
    effects_reconcile.add_argument("effect_key")
    effects_reconcile.add_argument("--resolution", choices=["confirmed", "failed"], required=True)
    effects_reconcile.add_argument("--details", help="objeto JSON com evidência da resolução")
    effects_reconcile.set_defaults(func=command_effects_reconcile)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ConversationError, PackageError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
