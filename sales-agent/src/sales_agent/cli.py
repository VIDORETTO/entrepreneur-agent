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
from typing import Any, Dict, List, Mapping, Optional

from . import __version__
from .channel import ChatwootBinding, ChatwootDeliveryProvider, ChatwootReceiver, FakeChatwootTransport
from .config import ConfigurationManager, load_manifest, load_package, promote_package, seed_examples, seed_package
from .conversation import ConversationError, SellerEngine
from .delivery import DeliveryProcessor
from .evaluation import EvaluationRunner, model_contract_check
from .governance import PilotController, QualitySupervisor
from .knowledge import FarolArtifactImporter, PersistentFarolKnowledge, StableFarolAdapter
from .model import HTTPModelAdapter, RuleBasedModel
from .skills import SkillCatalog
from .storage import StateStore
from .turns import TurnAssembler
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
            "stable_adapter": StableFarolAdapter().status(),
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


def command_restore_package(args: argparse.Namespace) -> int:
    result = ConfigurationManager(_store(args)).restore(args.business_id, args.storage_version)
    _print({key: value for key, value in result.items() if key != "package"})
    return 0


def command_configuration_inspect(args: argparse.Namespace) -> int:
    _print(ConfigurationManager(_store(args)).inspect(args.business_id))
    return 0


def command_configuration_diff(args: argparse.Namespace) -> int:
    candidate = load_package(args.package)
    _print(ConfigurationManager(_store(args)).diff(args.business_id, candidate))
    return 0


def command_configuration_simulate(args: argparse.Namespace) -> int:
    candidate = load_package(args.package)
    _print(ConfigurationManager(_store(args)).simulate(candidate, args.message, contact_id=args.contact_id))
    return 0


def command_skills_list(args: argparse.Namespace) -> int:
    skills = SkillCatalog().list_skills()
    _print({"skills": skills, "count": len(skills)})
    return 0


def command_skills_show(args: argparse.Namespace) -> int:
    value = SkillCatalog().read_skill(args.skill_id)
    _print(value)
    return 0 if value.get("available") else 2


def command_skills_doctor(args: argparse.Namespace) -> int:
    value = SkillCatalog().diagnose()
    _print(value)
    return 0 if value.get("ok") else 2


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
        capability=args.capability,
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
        "capability": payload.get("capability"),
        "blockers": payload.get("blockers", []),
        "checkpoint": payload.get("checkpoint", {}),
        "capabilities": payload.get("capabilities", {}),
    }


def _engine_for(store: StateStore, args: argparse.Namespace) -> SellerEngine:
    model = RuleBasedModel()
    endpoint = os.environ.get("SELLER_MODEL_URL")
    key = os.environ.get("SELLER_MODEL_API_KEY")
    model_name = os.environ.get("SELLER_MODEL_NAME", "configured-model")
    if endpoint and key and not getattr(args, "rules", False):
        model = HTTPModelAdapter(endpoint, key, model_name)  # type: ignore[assignment]
    supervisor = None
    setting = store.get_supervisor_setting()
    if setting and setting.get("mode") != "off":
        supervisor = QualitySupervisor(store)
    return SellerEngine(store, model=model, supervisor=supervisor)


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


def command_conversation_resume(args: argparse.Namespace) -> int:
    store = _store(args)
    result = _engine_for(store, args).resume(
        args.business_id,
        args.conversation_id,
        contact_id=args.contact_id,
        authority=args.authority,
        reason=args.reason,
    )
    _print(result)
    return 0 if result.get("resumed") else 2


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


def command_knowledge_reapprove(args: argparse.Namespace) -> int:
    store = _store(args)
    knowledge = PersistentFarolKnowledge(store)
    reapproved = knowledge.reapprove(args.business_id, args.source_id, args.version, args.reason)
    _print(
        {
            "reapproved": reapproved,
            "business_id": args.business_id,
            "source_id": args.source_id,
            "source_version": args.version,
            "reason": args.reason,
        }
    )
    return 0 if reapproved else 2


def command_knowledge_pending_reviews(args: argparse.Namespace) -> int:
    knowledge = PersistentFarolKnowledge(_store(args))
    items = knowledge.pending_reviews(args.business_id)
    _print({"items": items, "count": len(items), "status": "pending_review"})
    return 0


def command_knowledge_review(args: argparse.Namespace) -> int:
    knowledge = PersistentFarolKnowledge(_store(args))
    reviewed = knowledge.review_legacy(args.business_id, args.source_id, args.version, args.reason)
    _print(
        {
            "reviewed": reviewed,
            "business_id": args.business_id,
            "source_id": args.source_id,
            "source_version": args.version,
            "reason": args.reason,
        }
    )
    return 0 if reviewed else 2


def command_farol_import(args: argparse.Namespace) -> int:
    store = _store(args)
    importer = FarolArtifactImporter(PersistentFarolKnowledge(store))
    count = importer.import_package(args.business_id, args.path)
    _print({"imported_documents": count, "backend": "farol-artifact-v1", "business_id": args.business_id, "report": importer.last_report})
    return 0


def command_farol_status(args: argparse.Namespace) -> int:
    _print(StableFarolAdapter().status())
    return 0


def command_turn_receive(args: argparse.Namespace) -> int:
    store = _store(args)
    event = {
        "business_id": args.business_id,
        "conversation_id": args.conversation_id,
        "contact_id": args.contact_id,
        "channel": args.channel,
        "event_id": args.event_id,
        "text": args.message,
    }
    result = TurnAssembler(store, _engine_for(store, args)).receive(event, received_at=args.received_at)
    if hasattr(result.get("result"), "as_dict"):
        result["result"] = result["result"].as_dict()
    _print(result)
    return 0


def command_turn_process(args: argparse.Namespace) -> int:
    store = _store(args)
    results = TurnAssembler(store, _engine_for(store, args), window_seconds=args.window_seconds, max_wait_seconds=args.max_wait_seconds).process_due(now=args.now)
    _print({"results": [item.as_dict() for item in results], "count": len(results)})
    return 0


class _CLIProvider:
    def __init__(self, behavior: str):
        self.behavior = behavior

    def send(self, payload: Mapping[str, Any], *, idempotency_key: str) -> Mapping[str, Any]:
        if self.behavior in {"unknown", "timeout"}:
            return {"status": "unknown", "provider_id": "cli-fake-unknown"}
        if self.behavior == "rejected":
            return {"status": "rejected", "error": "cli fake provider rejected"}
        return {"status": "sent", "provider_id": "cli-fake-sent", "idempotency_key": idempotency_key}


def command_outbox_process(args: argparse.Namespace) -> int:
    store = _store(args)
    provider: Any = _CLIProvider(args.behavior)
    if args.channel == "chatwoot":
        provider = ChatwootDeliveryProvider(FakeChatwootTransport(behavior=args.behavior))
    pilot = PilotController(store) if args.channel == "chatwoot" else None
    outcomes = DeliveryProcessor(store, pilot=pilot).process_once(provider, limit=args.limit, lease_seconds=args.lease_seconds)
    _print({"outcomes": outcomes, "count": len(outcomes), "provider": args.behavior, "channel": args.channel})
    return 0 if all(item.get("status") in {"sent", "cancelled", "observed"} for item in outcomes) else 2


def command_chatwoot_admit(args: argparse.Namespace) -> int:
    raw = Path(args.body).read_bytes() if args.body else args.payload.encode("utf-8")
    binding = ChatwootBinding(args.business_id, args.account_id, args.inbox_id, args.secret)
    receiver = ChatwootReceiver(_store(args), [binding])
    result = receiver.admit(raw, {"X-Chatwoot-Signature": args.signature})
    _print(result)
    return 0 if result.get("ack") else 2


def command_pilot_configure(args: argparse.Namespace) -> int:
    cohort = json.loads(args.cohort) if args.cohort else {}
    limits = json.loads(args.limits) if args.limits else {}
    if not isinstance(cohort, dict) or not isinstance(limits, dict):
        raise ValueError("cohort e limits precisam ser objetos JSON")
    result = PilotController(_store(args)).configure(
        args.business_id,
        args.channel,
        mode=args.mode,
        cohort=cohort,
        limits=limits,
        evaluated_package_version=args.evaluated_package_version,
        evaluated_model=args.evaluated_model,
        evaluated_backend=args.evaluated_backend,
        authorize=args.authorize,
        reason=args.reason or "",
    )
    _print(result)
    return 0


def command_pilot_inspect(args: argparse.Namespace) -> int:
    _print(PilotController(_store(args)).inspect(args.business_id, args.channel))
    return 0


def command_pilot_interrupt(args: argparse.Namespace) -> int:
    _print(PilotController(_store(args)).interrupt(args.business_id, args.channel, reason=args.reason))
    return 0


def command_supervisor_list(args: argparse.Namespace) -> int:
    reviews = _store(args).list_supervisor_reviews(args.candidate_id)
    _print({"reviews": reviews, "count": len(reviews), "mode": "observation-only"})
    return 0


def command_supervisor_report(args: argparse.Namespace) -> int:
    supervisor = QualitySupervisor(_store(args), scope_key=args.scope_key)
    _print(supervisor.report(args.candidate_id))
    return 0


def command_supervisor_configure(args: argparse.Namespace) -> int:
    supervisor = QualitySupervisor(_store(args))
    _print(supervisor.configure(args.mode, policy=args.policy))
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
    candidate_package = load_package(args.package) if args.package else None
    runner = EvaluationRunner(
        Path(args.data_dir),
        model_name=args.model,
        backend_name=args.backend,
        channel=args.channel,
        candidate_package=candidate_package,
        candidate_business_id=args.business_id,
    )
    report = runner.run()
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print(report)
    return 0 if report["evaluation"]["thresholds_met"] else 2


def command_model_check(args: argparse.Namespace) -> int:
    if args.model is None:
        result = model_contract_check()
    else:
        factory = EvaluationRunner.MODEL_NAMES[args.model]
        result = model_contract_check(factory())
    _print(result)
    return 0 if result.get("passed") else 2


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
    acknowledged = _store(args).ack_outbox(args.message_key, lease_owner=args.lease_owner)
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
        lease_owner=args.lease_owner,
    )
    _print({"message_key": args.message_key, "status": status})
    return 0


def command_outbox_recover(args: argparse.Namespace) -> int:
    count = _store(args).recover_expired_outbox()
    _print({"recovered": count})
    return 0


def command_outbox_reconcile(args: argparse.Namespace) -> int:
    details = json.loads(args.details) if args.details else {}
    if not isinstance(details, dict):
        raise ValueError("details precisa ser um objeto JSON")
    result = _store(args).reconcile_outbox(args.message_key, args.resolution, details)
    _print(result)
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
    restore_cmd = sub.add_parser("restore-package", help="restaurar uma versão histórica como nova promoção")
    restore_cmd.add_argument("--business-id", required=True)
    restore_cmd.add_argument("--storage-version", type=int, required=True)
    restore_cmd.set_defaults(func=command_restore_package)

    configure = sub.add_parser("configure", help="entrevista persistente do dono")
    configure_sub = configure.add_subparsers(dest="configure_command", required=True)
    start = configure_sub.add_parser("start")
    start.add_argument("--business-id", required=True)
    start.add_argument("--business-name")
    start.add_argument("--template", choices=["physical", "b2b", "service", "digital"], default="physical")
    start.add_argument("--material", action="append")
    start.add_argument("--session-id")
    start.add_argument("--capability", default="checkout_prepare")
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
    config_inspect = configure_sub.add_parser("inspect")
    config_inspect.add_argument("--business-id", required=True)
    config_inspect.set_defaults(func=command_configuration_inspect)
    config_diff = configure_sub.add_parser("diff")
    config_diff.add_argument("--business-id", required=True)
    config_diff.add_argument("package")
    config_diff.set_defaults(func=command_configuration_diff)
    config_simulate = configure_sub.add_parser("simulate")
    config_simulate.add_argument("package")
    config_simulate.add_argument("--message", required=True)
    config_simulate.add_argument("--contact-id", default="verified:simulation")
    config_simulate.set_defaults(func=command_configuration_simulate)
    config_restore = configure_sub.add_parser("restore")
    config_restore.add_argument("--business-id", required=True)
    config_restore.add_argument("--storage-version", type=int, required=True)
    config_restore.set_defaults(func=command_restore_package)

    skills = sub.add_parser("skills", help="inspecionar skills instaladas")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)
    skills_list = skills_sub.add_parser("list")
    skills_list.set_defaults(func=command_skills_list)
    skills_show = skills_sub.add_parser("show")
    skills_show.add_argument("skill_id")
    skills_show.set_defaults(func=command_skills_show)
    skills_doctor = skills_sub.add_parser("doctor")
    skills_doctor.set_defaults(func=command_skills_doctor)

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

    conversation = sub.add_parser("conversation", help="controles explícitos da conversa")
    conversation_sub = conversation.add_subparsers(dest="conversation_command", required=True)
    conversation_resume = conversation_sub.add_parser("resume", help="liberar uma pausa humana explicitamente")
    conversation_resume.add_argument("--business-id", required=True)
    conversation_resume.add_argument("--conversation-id", required=True)
    conversation_resume.add_argument("--contact-id", required=True)
    conversation_resume.add_argument("--authority", required=True)
    conversation_resume.add_argument("--reason", required=True)
    conversation_resume.set_defaults(func=command_conversation_resume)

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
    reapprove = knowledge_sub.add_parser("reapprove")
    reapprove.add_argument("--business-id", required=True)
    reapprove.add_argument("--source-id", required=True)
    reapprove.add_argument("--version")
    reapprove.add_argument("--reason", required=True)
    reapprove.set_defaults(func=command_knowledge_reapprove)
    pending_reviews = knowledge_sub.add_parser("pending-reviews")
    pending_reviews.add_argument("--business-id")
    pending_reviews.set_defaults(func=command_knowledge_pending_reviews)
    review = knowledge_sub.add_parser("review")
    review.add_argument("--business-id", required=True)
    review.add_argument("--source-id", required=True)
    review.add_argument("--version", required=True)
    review.add_argument("--reason", required=True)
    review.set_defaults(func=command_knowledge_review)

    farol = sub.add_parser("farol", help="importar artefatos gerados pelo Farol")
    farol_sub = farol.add_subparsers(dest="farol_command", required=True)
    farol_import = farol_sub.add_parser("import")
    farol_import.add_argument("--business-id", required=True)
    farol_import.add_argument("path")
    farol_import.set_defaults(func=command_farol_import)
    farol_status = farol_sub.add_parser("status")
    farol_status.set_defaults(func=command_farol_status)

    demo = sub.add_parser("demo", help="executar as quatro demonstrações fictícias")
    demo.add_argument("--persist", action="store_true", help="manter o estado da demonstração em --data-dir")
    demo.set_defaults(func=command_demo)
    evaluate = sub.add_parser("evaluate", help="executar cenários AC e gerar relatório")
    evaluate.add_argument("--output")
    evaluate.add_argument("--model", choices=sorted(EvaluationRunner.MODEL_NAMES), default="rules-v1")
    evaluate.add_argument("--backend", choices=["sqlite-farol-v1"], default="sqlite-farol-v1")
    evaluate.add_argument("--channel", default="evaluation")
    evaluate.add_argument("--package", help="arquivo JSON do pacote candidato")
    evaluate.add_argument("--business-id", help="identificador do negócio do pacote candidato")
    evaluate.set_defaults(func=command_evaluate)
    model_check = sub.add_parser("model-check", help="testar contrato do adaptador de modelo")
    model_check.add_argument("--model", choices=sorted(EvaluationRunner.MODEL_NAMES))
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
    outbox_list.add_argument("--status", choices=["pending", "processing", "sent", "cancelled", "dead_letter", "unknown", "observed"])
    outbox_list.set_defaults(func=command_outbox_list)
    outbox_claim = outbox_sub.add_parser("claim")
    outbox_claim.add_argument("--limit", type=int, default=10)
    outbox_claim.add_argument("--lease-seconds", type=int, default=60)
    outbox_claim.set_defaults(func=command_outbox_claim)
    outbox_ack = outbox_sub.add_parser("ack")
    outbox_ack.add_argument("message_key")
    outbox_ack.add_argument("--lease-owner")
    outbox_ack.set_defaults(func=command_outbox_ack)
    outbox_nack = outbox_sub.add_parser("nack")
    outbox_nack.add_argument("message_key")
    outbox_nack.add_argument("--error", required=True)
    outbox_nack.add_argument("--max-attempts", type=int, default=5)
    outbox_nack.add_argument("--delay-seconds", type=int, default=30)
    outbox_nack.add_argument("--lease-owner")
    outbox_nack.set_defaults(func=command_outbox_nack)
    outbox_recover = outbox_sub.add_parser("recover")
    outbox_recover.set_defaults(func=command_outbox_recover)
    outbox_reconcile = outbox_sub.add_parser("reconcile", help="conciliar uma entrega com resultado desconhecido")
    outbox_reconcile.add_argument("message_key")
    outbox_reconcile.add_argument("--resolution", choices=["sent", "cancelled", "dead_letter"], required=True)
    outbox_reconcile.add_argument("--details", help="objeto JSON com evidência do provedor")
    outbox_reconcile.set_defaults(func=command_outbox_reconcile)
    outbox_process = outbox_sub.add_parser("process", help="executar ciclo com provedor falso explícito")
    outbox_process.add_argument("--limit", type=int, default=10)
    outbox_process.add_argument("--lease-seconds", type=int, default=60)
    outbox_process.add_argument("--behavior", choices=["sent", "unknown", "timeout", "rejected"], default="sent")
    outbox_process.add_argument("--channel", choices=["local", "chatwoot"], default="local")
    outbox_process.set_defaults(func=command_outbox_process)

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

    turns = sub.add_parser("turn", help="receber e processar turnos duráveis")
    turns_sub = turns.add_subparsers(dest="turn_command", required=True)
    turn_receive = turns_sub.add_parser("receive")
    turn_receive.add_argument("--business-id", required=True)
    turn_receive.add_argument("--conversation-id", required=True)
    turn_receive.add_argument("--contact-id", required=True)
    turn_receive.add_argument("--event-id", required=True)
    turn_receive.add_argument("--message", required=True)
    turn_receive.add_argument("--channel", default="cli")
    turn_receive.add_argument("--received-at")
    turn_receive.add_argument("--rules", action="store_true")
    turn_receive.set_defaults(func=command_turn_receive)
    turn_process = turns_sub.add_parser("process")
    turn_process.add_argument("--now")
    turn_process.add_argument("--window-seconds", type=int, default=3)
    turn_process.add_argument("--max-wait-seconds", type=int, default=15)
    turn_process.add_argument("--rules", action="store_true")
    turn_process.set_defaults(func=command_turn_process)

    channel = sub.add_parser("channel", help="contratos de canais externos")
    channel_sub = channel.add_subparsers(dest="channel_command", required=True)
    chatwoot = channel_sub.add_parser("chatwoot-admit")
    chatwoot.add_argument("--business-id", required=True)
    chatwoot.add_argument("--account-id", required=True)
    chatwoot.add_argument("--inbox-id", required=True)
    chatwoot.add_argument("--secret", required=True)
    body_group = chatwoot.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body")
    body_group.add_argument("--payload")
    chatwoot.add_argument("--signature", required=True)
    chatwoot.set_defaults(func=command_chatwoot_admit)

    pilot = sub.add_parser("pilot", help="modos graduais e interrupção")
    pilot_sub = pilot.add_subparsers(dest="pilot_command", required=True)
    pilot_config = pilot_sub.add_parser("configure")
    pilot_config.add_argument("--business-id", required=True)
    pilot_config.add_argument("--channel", default="chatwoot")
    pilot_config.add_argument("--mode", choices=["observation", "assistance", "pilot"], default="observation")
    pilot_config.add_argument("--cohort")
    pilot_config.add_argument("--limits")
    pilot_config.add_argument("--evaluated-package-version")
    pilot_config.add_argument("--evaluated-model")
    pilot_config.add_argument("--evaluated-backend")
    pilot_config.add_argument("--authorize", action="store_true")
    pilot_config.add_argument("--reason", default="")
    pilot_config.set_defaults(func=command_pilot_configure)
    pilot_inspect = pilot_sub.add_parser("inspect")
    pilot_inspect.add_argument("--business-id", required=True)
    pilot_inspect.add_argument("--channel", default="chatwoot")
    pilot_inspect.set_defaults(func=command_pilot_inspect)
    pilot_interrupt = pilot_sub.add_parser("interrupt")
    pilot_interrupt.add_argument("--business-id", required=True)
    pilot_interrupt.add_argument("--channel", default="chatwoot")
    pilot_interrupt.add_argument("--reason", default="interrompido pelo operador")
    pilot_interrupt.set_defaults(func=command_pilot_interrupt)

    supervisor = sub.add_parser("supervisor", help="listar observações de qualidade")
    supervisor_sub = supervisor.add_subparsers(dest="supervisor_command", required=True)
    supervisor_configure = supervisor_sub.add_parser("configure")
    supervisor_configure.add_argument("--mode", choices=["off", "observation", "selective"], required=True)
    supervisor_configure.add_argument("--policy", choices=["optional", "mandatory"], default="optional")
    supervisor_configure.set_defaults(func=command_supervisor_configure)
    supervisor_list = supervisor_sub.add_parser("list")
    supervisor_list.add_argument("--candidate-id")
    supervisor_list.set_defaults(func=command_supervisor_list)
    supervisor_report = supervisor_sub.add_parser("report")
    supervisor_report.add_argument("--candidate-id")
    supervisor_report.add_argument("--scope-key", default="global")
    supervisor_report.set_defaults(func=command_supervisor_report)
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
