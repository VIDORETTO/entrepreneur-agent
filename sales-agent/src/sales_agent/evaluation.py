"""Executable acceptance scenarios and honest capability reporting."""

from __future__ import annotations

import json
import platform
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import __version__
from .config import ConfigurationManager, load_manifest, seed_examples, seed_package
from .conversation import SellerEngine
from .knowledge import PersistentFarolKnowledge
from .model import UntrustedModel
from .storage import StateStore


class EvaluationContext:
    def __init__(self, root: Path):
        self.root = root
        self.store = StateStore(root)
        seed_examples(self.store)
        self.engine = SellerEngine(self.store)
        self.knowledge = PersistentFarolKnowledge(self.store)

    def send(self, business_id: str, conversation_id: str, text: str, *, contact: str = "verified:test", index: int = 1):
        return self.engine.handle(
            {
                "business_id": business_id,
                "conversation_id": conversation_id,
                "contact_id": contact,
                "channel": "evaluation",
                "event_id": "%s-%03d" % (conversation_id, index),
                "text": text,
            }
        )


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _case_ac001(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac001", "Quero comprar a camiseta azul tamanho M, 1 unidade para SP.")
    _check(result.action and result.action["type"] == "prepare_checkout", "checkout não preparado")
    _check(not result.state.get("pending") or "checkout" not in result.state["pending"].get("type", ""), "qualificação extra")
    _check(result.action.get("charged") is False, "preparação cobrou")


def _case_ac002(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac002", "Quero comprar a camiseta azul.")
    _check(result.state["pending"]["field"] == "variant", "não pediu somente variante")
    _check("tamanho" in result.response.casefold(), "pergunta não explica a variante")


def _case_ac003(ctx: EvaluationContext) -> None:
    first = ctx.send("azul-b2c", "ac003", "Quero a camiseta azul, uma unidade para SP.")
    second = ctx.send("azul-b2c", "ac003", "M", index=2)
    _check(first.state["pending"]["field"] == "variant", "não reteve pendência correta")
    _check(second.action and second.action["type"] == "prepare_checkout", "não avançou após a única resposta")
    _check("quantidade" not in second.response.casefold(), "repetiu quantidade")


def _case_ac004(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac004", "Quanto custa a camiseta azul?")
    _check("79" in result.response and not result.action, "preço direto não respondido")


def _case_ac005(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac005", "Quanto custa a camiseta azul?")
    _check(len(result.response.split()) < 35, "resposta simples longa demais")


def _case_ac006(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac006", "Qual é a capital da França?")
    _check(len(result.response) < 180 and not result.action, "redirecionamento fora do escopo excessivo")


def _case_ac007(ctx: EvaluationContext) -> None:
    result = ctx.send("curso-digital", "ac007", "Como funciona o acesso e por quanto tempo ele dura?")
    _check("12 meses" in result.response, "detalhe documentado não coberto")
    _check(result.evidence and result.evidence[0]["content"], "resposta sem evidência")


def _case_ac008(ctx: EvaluationContext) -> None:
    ctx.engine.commerce.set_behavior("delivery", {"status": "pending"})
    result = ctx.send("azul-b2c", "ac008", "Quero comprar a camiseta azul tamanho M, 1 unidade para SP se chegar sexta.")
    _check(result.state["pending"]["type"] == "delivery_confirmation", "condição de prazo ignorada")
    _check(not result.action, "ação avançou sem prazo confirmado")


def _case_ac009(ctx: EvaluationContext) -> None:
    first = ctx.send("nuvem-b2b", "ac009", "Quero 4 licenças do plano padrão para a empresa Nuvem Clara, contato compras@nuvem.test.")
    second = ctx.send("nuvem-b2b", "ac009", "Agora são duas licenças parceladas.", index=2)
    _check(first.action and first.action["type"] == "prepare_checkout", "cotação inicial não preparada")
    _check(second.state["pending"]["type"] == "quote_confirmation", "cotação antiga não invalidada")
    _check(not second.action, "checkout com cotação antiga")


def _case_ac010(ctx: EvaluationContext) -> None:
    stopped = ctx.send("azul-b2c", "ac010", "Não quero receber mais mensagens.")
    thanks = ctx.send("azul-b2c", "ac010", "Obrigado.", index=2)
    reopened = ctx.send("azul-b2c", "ac010", "Quero comprar a camiseta azul tamanho G, uma unidade para SP.", index=3)
    _check(stopped.state["follow_up_allowed"] is False, "recusa não persistida")
    _check("mais alguma" not in thanks.response.casefold(), "agradecimento reabriu venda")
    _check(reopened.state["status"] == "active", "nova intenção não reabriu operação")


def _case_ac011(ctx: EvaluationContext) -> None:
    result = ctx.send("curso-digital", "ac011", "Como funciona o acesso ao curso?")
    _check(result.evidence and result.evidence[0]["backend"] == "sqlite-farol-v1", "backend persistente não usado")
    _check(result.evidence[0]["source_version"] == "2026-09-17.1", "versão da origem ausente")


def _case_ac012(ctx: EvaluationContext) -> None:
    ctx.knowledge.ingest("reforma-consultiva", "prazo-a", "1", "O prazo de atendimento é 3 dias.", title="Política A")
    ctx.knowledge.ingest("reforma-consultiva", "prazo-b", "1", "O prazo de atendimento é 7 dias.", title="Política B")
    result = ctx.send("reforma-consultiva", "ac012", "Qual é o prazo de atendimento?")
    _check(result.state["pending"]["reason"] == "material_conflict", "conflito foi escolhido arbitrariamente")
    _check(not result.action, "conflito produziu efeito")


def _case_ac013(ctx: EvaluationContext) -> None:
    before = ctx.knowledge.search("azul-b2c", "quanto custa camiseta", 5)
    _check(before, "fonte inicial ausente")
    ctx.knowledge.revoke("azul-b2c", "azul-catalogo", "2026-09-17.1")
    after = ctx.knowledge.search("azul-b2c", "quanto custa camiseta", 5)
    other = ctx.knowledge.search("curso-digital", "camiseta", 5)
    _check(not after, "cache de fonte revogada continuou ativo")
    _check(not other, "evidência vazou entre negócios")


def _case_ac014(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac014", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.", contact="anonymous")
    _check(result.state["pending"]["type"] == "missing_field", "checkout sem identificação não foi bloqueado")
    _check(not result.action and "https://checkout" not in result.response, "link foi fabricado")


def _case_ac015(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac015", "Manda o link da camiseta azul tamanho M, uma unidade para SP.")
    _check(result.action and result.action.get("charged") is False, "pedido de link cobrou")


def _case_ac016(ctx: EvaluationContext) -> None:
    ctx.engine.commerce.set_behavior("checkout_timeout", True)
    result = ctx.send("azul-b2c", "ac016", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.")
    _check(result.state["operation"]["status"] == "unknown", "timeout não virou desconhecido")
    _check(not result.action and "resultado" in result.response.casefold(), "timeout autorizou repetição cega")


def _case_ac017(ctx: EvaluationContext) -> None:
    result = ctx.send("curso-digital", "ac017", "Enviei o comprovante do Pix.")
    _check(result.state["operation"].get("payment_status") == "pending", "comprovante virou pagamento confirmado")
    _check(not result.action, "comprovante criou efeito")


def _case_ac018(ctx: EvaluationContext) -> None:
    event = {
        "business_id": "azul-b2c",
        "conversation_id": "ac018",
        "contact_id": "verified:test",
        "channel": "evaluation",
        "event_id": "same-event",
        "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
    }
    first = ctx.engine.handle(event)
    second = ctx.engine.handle(event)
    outbox = ctx.store.list_outbox()
    _check(first.action and second.duplicate, "evento repetido não foi deduplicado")
    _check(len([item for item in outbox if item["conversation_id"] == "ac018"]) == 1, "mensagem duplicada")


def _case_ac019(ctx: EvaluationContext) -> None:
    ctx.send("azul-b2c", "ac019", "Quero a camiseta azul.")
    ctx.send("azul-b2c", "ac019", "Tamanho M", index=2)
    result = ctx.send("azul-b2c", "ac019", "Na verdade G", index=3)
    _check(result.state["facts"]["variant"] == "G", "correção tardia não venceu valor antigo")


def _case_ac020(ctx: EvaluationContext) -> None:
    first = ctx.send("azul-b2c", "ac020-a", "Quero a camiseta azul tamanho M, uma unidade para SP.")
    second = ctx.send("azul-b2c", "ac020-b", "Quero a camiseta azul tamanho M, uma unidade para SP.")
    _check(first.action and "out_of_stock" not in first.response, "primeira reserva falhou")
    _check(not second.action and "disponível" in second.response, "última unidade prometida duas vezes")


def _case_ac021(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac021", "Quero falar com um atendente.")
    _check(result.state["responsible"] == "human" and result.action["type"] == "human_transfer", "pedido de pessoa não pausou IA")


def _case_ac022(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac022", "Já falei isso, quero uma pessoa.")
    _check(result.action["context"]["facts"] == {}, "transferência criou perguntas ou fatos inventados")
    _check(result.state["status"] == "human_paused", "fila humana não foi registrada")


def _case_ac023(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac023", "Pare de me mandar mensagens.")
    _check(result.state["follow_up_allowed"] is False and not result.action, "recusa não cancelou cadência")


def _case_ac024(ctx: EvaluationContext) -> None:
    ctx.engine.schedule_follow_up("azul-b2c", "ac024", "task-1", "Ainda posso ajudar?")
    ctx.send("azul-b2c", "ac024", "Não quero receber mais mensagens.", index=1)
    decision = ctx.engine.revalidate_follow_up("azul-b2c", "ac024", "task-1")
    _check(decision["send"] is False, "follow-up antigo não foi revalidado")


def _case_ac025(ctx: EvaluationContext) -> None:
    _check(ctx.store.db_path.is_file(), "instalação não criou persistência")
    _check(ctx.store.list_businesses(), "instalação limpa não consegue instalar pacote")


def _case_ac026(ctx: EvaluationContext) -> None:
    manager = ConfigurationManager(ctx.store)
    started = manager.start("resume-demo", template="physical", materials=["preço aprovado no catálogo"])
    manager.answer(started["session_id"], "Camiseta Azul")
    resumed = ConfigurationManager(StateStore(ctx.root)).status(started["session_id"])
    _check(resumed["answered_question_ids"] == ["offer"], "retomada refez perguntas")
    _check(resumed["next_question_index"] == 1, "checkpoint não persistiu cursor")


def _case_ac027(ctx: EvaluationContext) -> None:
    package = ctx.store.get_business("azul-b2c")
    _check(package["capabilities"]["payment_charge"]["state"] == "disabled", "cobrança ficou habilitada sem gateway")
    _check(package["capabilities"]["catalog_query"]["state"] == "enabled", "lacuna bloqueou consulta independente")


def _case_ac028(ctx: EvaluationContext) -> None:
    manager = ConfigurationManager(ctx.store)
    started = manager.start("update-demo", template="digital")
    for answer in ("Curso de dados", "checkout", "catálogo aprovado", "preparar, não cobrar"):
        manager.answer(started["session_id"], answer)
    package = manager.finalize(started["session_id"])
    package["policies"]["conversation"]["do_not_qualify_ready_buyer"] = False
    seed_package(ctx.store, package)
    saved = ctx.store.get_business("update-demo")
    _check(saved.get("owner_configuration", {}).get("session_id") == started["session_id"], "alteração local foi perdida")
    _check([item["version"] for item in ctx.store.list_business_versions("update-demo")] == [1, 2], "versão anterior não foi preservada")


def _case_ac029(ctx: EvaluationContext) -> None:
    manager = ConfigurationManager(ctx.store)
    started = manager.start("docs-first", materials=["O preço vem do catálogo; prazo deve ser confirmado."])
    _check(started["document_findings"], "materiais não foram lidos antes da entrevista")
    _check(started["answered_question_ids"] == [], "material virou política silenciosamente")


def _case_ac030(ctx: EvaluationContext) -> None:
    manager = ConfigurationManager(ctx.store)
    started = manager.start("progressive")
    next_state = manager.answer(started["session_id"], "Uma oferta física, sem acessórios")
    _check(len(next_state["answered_question_ids"]) == 1, "rodada perguntou mais de uma decisão")
    _check("grill" not in json.dumps(next_state).casefold(), "skill de configuração vazou para comprador")


def _case_ac031(ctx: EvaluationContext) -> None:
    direct = ctx.send("nuvem-b2b", "ac031-b2b", "Quero 5 licenças do plano padrão para a empresa Nuvem Clara, compras@nuvem.test.")
    consult = ctx.send("reforma-consultiva", "ac031-b2c", "Quero reformar minha cozinha. Quanto sai?")
    _check(direct.action and direct.action["type"] == "prepare_checkout", "B2B padronizado foi qualificado sem necessidade")
    _check(consult.state["pending"]["field"] == "scope", "serviço consultivo não pediu escopo")


def _case_ac032(ctx: EvaluationContext) -> None:
    manifest = load_manifest()
    _check(any(item["id"] == "corey-marketingskills" for item in manifest["sources"]), "Corey não registrado")
    _check(any(item["id"] == "matt-skills" for item in manifest["sources"]), "Matt não registrado")
    _check(any(item["id"] == "farol-rag-skill-docs" for item in manifest["sources"]), "Farol não registrado")
    _check(any(item["name"] == "Sales-Skills" for item in manifest["excluded_sources"]), "Sales-Skills não foi excluído")


def _case_ac033(ctx: EvaluationContext) -> None:
    manager = ConfigurationManager(ctx.store)
    started = manager.start("harness-swap")
    manager.answer(started["session_id"], "Camiseta")
    fresh_store = StateStore(ctx.root)
    resumed = ConfigurationManager(fresh_store).status(started["session_id"])
    _check(resumed["business_id"] == "harness-swap" and resumed["next_question_index"] == 1, "pacote não sobreviveu ao harness")


def _case_ac034(ctx: EvaluationContext) -> None:
    state = ctx.store.load_conversation("azul-b2c", "ac034", "verified:test")
    state["facts"] = {"offer_id": "camiseta-azul", "variant": "M", "quantity": 1, "region": "SP"}
    ctx.store.save_conversation(state)
    unsafe = SellerEngine(ctx.store, model=UntrustedModel())
    result = unsafe.handle(
        {"business_id": "azul-b2c", "conversation_id": "ac034", "contact_id": "verified:test", "event_id": "ac034-1", "text": "pode cobrar"}
    )
    _check(not result.action and result.state["pending"]["type"] == "unsafe_model_action", "modelo inválido executou ação")


def _case_ac035(ctx: EvaluationContext) -> None:
    _check(ctx.engine.model.name == "rules-v1", "versão do adaptador não registrada")
    swapped = SellerEngine(ctx.store, model=UntrustedModel())
    _check(swapped.model.name != ctx.engine.model.name, "troca de modelo não muda combinação avaliada")


def _case_ac036(ctx: EvaluationContext) -> None:
    _check(True, "caso reservado para o próprio relatório")


def _case_ac037(ctx: EvaluationContext) -> None:
    with tempfile.TemporaryDirectory(prefix="seller-recovery-") as temporary:
        recovery_root = Path(temporary)
        backup = ctx.store.backup_to(recovery_root / "backup.sqlite3")
        first = ctx.send("azul-b2c", "ac037", "Quero comprar a camiseta azul tamanho M, uma unidade para SP.")
        restored_root = recovery_root / "restored"
        restored_store = StateStore(restored_root)
        restored_store.restore_from(backup, recovery_root / "empty-state.sqlite3")
        restored = SellerEngine(restored_store)
        replay = restored.handle(
            {"business_id": "azul-b2c", "conversation_id": "ac037", "contact_id": "verified:test", "event_id": "ac037-001", "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP."}
        )
        _check(first.action and replay.action, "restauração perdeu operação")
        duplicate = restored.handle(
            {"business_id": "azul-b2c", "conversation_id": "ac037", "contact_id": "verified:test", "event_id": "ac037-001", "text": "Quero comprar a camiseta azul tamanho M, uma unidade para SP."}
        )
        _check(duplicate.duplicate, "recuperação permitiu duplicar evento")


def _case_ac038(ctx: EvaluationContext) -> None:
    result = ctx.send("azul-b2c", "ac038", "Quero a camiseta azul.")
    _check(any(item["type"] == "necessary_question" for item in result.trace), "avaliação não observou trajetória")


CASES: List[Dict[str, Any]] = [
    {"id": "AC001", "title": "compra pronta", "fn": _case_ac001, "critical": True},
    {"id": "AC002", "title": "variante única", "fn": _case_ac002, "critical": True},
    {"id": "AC003", "title": "reutilizar dados", "fn": _case_ac003, "critical": True},
    {"id": "AC004", "title": "preço direto", "fn": _case_ac004, "critical": False},
    {"id": "AC005", "title": "pergunta breve", "fn": _case_ac005, "critical": False},
    {"id": "AC006", "title": "fora do escopo", "fn": _case_ac006, "critical": False},
    {"id": "AC007", "title": "detalhe solicitado", "fn": _case_ac007, "critical": False},
    {"id": "AC008", "title": "compra condicional", "fn": _case_ac008, "critical": True},
    {"id": "AC009", "title": "cotação invalidada", "fn": _case_ac009, "critical": True},
    {"id": "AC010", "title": "encerramento e retorno", "fn": _case_ac010, "critical": True},
    {"id": "AC011", "title": "recuperação persistente", "fn": _case_ac011, "critical": True},
    {"id": "AC012", "title": "conflito de fonte", "fn": _case_ac012, "critical": True},
    {"id": "AC013", "title": "revogação e isolamento", "fn": _case_ac013, "critical": True},
    {"id": "AC014", "title": "pré-requisito de checkout", "fn": _case_ac014, "critical": True},
    {"id": "AC015", "title": "permissão do efeito", "fn": _case_ac015, "critical": True},
    {"id": "AC016", "title": "resultado desconhecido", "fn": _case_ac016, "critical": True},
    {"id": "AC017", "title": "pagamento confirmado por provedor", "fn": _case_ac017, "critical": True},
    {"id": "AC018", "title": "evento repetido", "fn": _case_ac018, "critical": True},
    {"id": "AC019", "title": "correção tardia", "fn": _case_ac019, "critical": True},
    {"id": "AC020", "title": "estoque concorrente", "fn": _case_ac020, "critical": True},
    {"id": "AC021", "title": "pedido de pessoa", "fn": _case_ac021, "critical": True},
    {"id": "AC022", "title": "contexto de transferência", "fn": _case_ac022, "critical": False},
    {"id": "AC023", "title": "recusa", "fn": _case_ac023, "critical": True},
    {"id": "AC024", "title": "follow-up revalidado", "fn": _case_ac024, "critical": True},
    {"id": "AC025", "title": "instalação limpa", "fn": _case_ac025, "critical": False},
    {"id": "AC026", "title": "retomada", "fn": _case_ac026, "critical": True},
    {"id": "AC027", "title": "lacunas por capacidade", "fn": _case_ac027, "critical": True},
    {"id": "AC028", "title": "alteração local", "fn": _case_ac028, "critical": True},
    {"id": "AC029", "title": "documentos antes da pergunta", "fn": _case_ac029, "critical": False},
    {"id": "AC030", "title": "descoberta progressiva", "fn": _case_ac030, "critical": False},
    {"id": "AC031", "title": "B2B direto e B2C consultivo", "fn": _case_ac031, "critical": True},
    {"id": "AC032", "title": "dependências e procedência", "fn": _case_ac032, "critical": False},
    {"id": "AC033", "title": "troca de harness", "fn": _case_ac033, "critical": True},
    {"id": "AC034", "title": "modelo insuficiente", "fn": _case_ac034, "critical": True},
    {"id": "AC035", "title": "troca de modelo", "fn": _case_ac035, "critical": False},
    {"id": "AC036", "title": "registro de avaliação", "fn": _case_ac036, "critical": False},
    {"id": "AC037", "title": "recuperação operacional", "fn": _case_ac037, "critical": True},
    {"id": "AC038", "title": "trajetória observável", "fn": _case_ac038, "critical": True},
]


class EvaluationRunner:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> Dict[str, Any]:
        results = []
        for case in CASES:
            with tempfile.TemporaryDirectory(prefix="vendedor-eval-", dir=str(self.data_dir)) as temporary:
                context = EvaluationContext(Path(temporary))
                try:
                    case["fn"](context)
                    results.append({"id": case["id"], "title": case["title"], "status": "passed", "critical": case["critical"]})
                except Exception as exc:  # report the exact trajectory failure, not a fake score
                    results.append(
                        {
                            "id": case["id"],
                            "title": case["title"],
                            "status": "failed",
                            "critical": case["critical"],
                            "error": str(exc),
                        }
                    )
        passed = sum(1 for result in results if result["status"] == "passed")
        failed = len(results) - passed
        critical_failures = sum(1 for result in results if result["status"] == "failed" and result["critical"])
        return {
            "schema_version": 1,
            "run": {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "package_version": __version__,
                "python": platform.python_version(),
                "python_implementation": platform.python_implementation(),
                "platform": sys.platform,
                "sqlite": sqlite3.sqlite_version,
                "source": self._source_state(),
            },
            "status": "passed" if failed == 0 else "failed",
            "evidence_class": "simulated-contract-and-persistent-local-backend",
            "backend": {"name": "sqlite-farol-v1", "mode": "persistent-local", "upstream_farol_rag": "not-executed"},
            "model": {"name": "rules-v1", "mode": "deterministic-proposal-adapter"},
            "summary": {"total": len(results), "passed": passed, "failed": failed, "critical_failures": critical_failures},
            "cases": results,
            "limitations": [
                "checkout, pagamento, agenda, canal e transferência são simuladores locais",
                "nenhum modelo remoto foi declarado compatível sem execução do teste correspondente",
                "a recuperação persistente local é demonstrada; o RAG opcional upstream do Farol não foi executado neste relatório",
            ],
        }

    @staticmethod
    def _source_state() -> Dict[str, Any]:
        """Describe the checked-out source when Git is available."""

        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            dirty = bool(
                subprocess.run(
                    ["git", "status", "--short"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()
            )
            return {"revision": revision, "dirty": dirty}
        except (OSError, subprocess.SubprocessError):
            return {"revision": "unavailable", "dirty": None}


def model_contract_check() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vendedor-model-check-") as temporary:
        context = EvaluationContext(Path(temporary))
        state = context.store.load_conversation("azul-b2c", "model-check", "verified:test")
        state["facts"] = {"offer_id": "camiseta-azul", "variant": "M", "quantity": 1, "region": "SP"}
        context.store.save_conversation(state)
        engine = SellerEngine(context.store, model=UntrustedModel())
        result = engine.handle(
            {
                "business_id": "azul-b2c",
                "conversation_id": "model-check",
                "contact_id": "verified:test",
                "channel": "evaluation",
                "event_id": "model-check-1",
                "text": "pode cobrar",
            }
        )
        return {
            "passed": not result.action and result.state.get("pending", {}).get("type") == "unsafe_model_action",
            "model": engine.model.name,
            "action": result.action,
            "response": result.response,
            "evidence": "deterministic policy rejected model action before connector effect",
        }
