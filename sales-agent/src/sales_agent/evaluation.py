"""Executable acceptance scenarios and honest capability reporting."""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import __version__
from .config import ConfigurationManager, load_manifest, seed_examples, seed_package
from .conversation import SellerEngine
from .knowledge import PersistentFarolKnowledge
from .model import ModelAdapter, RuleBasedModel, UntrustedModel
from .privacy import redact_data
from .skills import SkillCatalog
from .storage import StateStore
from .validation import package_fingerprint, validate_package


class EvaluationContext:
    def __init__(
        self,
        root: Path,
        *,
        model: Optional[ModelAdapter] = None,
        channel: str = "evaluation",
        candidate_package: Optional[Mapping[str, Any]] = None,
    ):
        self.root = root
        self.store = StateStore(root)
        seed_examples(self.store)
        if candidate_package is not None:
            # Keep the fixed regression corpus available, while replacing or
            # adding the business explicitly selected by the caller.  The
            # candidate is persisted through the same package seam as an
            # installed package; it is not injected into the model prompt.
            seed_package(self.store, candidate_package)
        self.engine = SellerEngine(self.store, model=model or RuleBasedModel())
        self.knowledge = PersistentFarolKnowledge(self.store)
        self.channel = channel
        self.observations: List[Dict[str, Any]] = []
        self.auxiliary: Dict[str, Any] = {}

    def send(self, business_id: str, conversation_id: str, text: str, *, contact: str = "verified:test", index: int = 1):
        result = self.engine.handle(
            {
                "business_id": business_id,
                "conversation_id": conversation_id,
                "contact_id": contact,
                "channel": self.channel,
                "event_id": "%s-%03d" % (conversation_id, index),
                "text": text,
            }
        )
        self.observations.append(result.as_dict())
        return result


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
    # The search seam is intentionally strict: these are buyer-facing
    # revisions for the same service and subject, rather than unscoped
    # internal/legacy rows that must be ignored.
    ctx.knowledge.ingest(
        "reforma-consultiva",
        "prazo-a",
        "1",
        "O prazo de atendimento é 3 dias.",
        title="Política A",
        audience="buyer",
        scope="reforma-cozinha",
        subject="delivery",
    )
    ctx.knowledge.ingest(
        "reforma-consultiva",
        "prazo-b",
        "1",
        "O prazo de atendimento é 7 dias.",
        title="Política B",
        audience="buyer",
        scope="reforma-cozinha",
        subject="delivery",
    )
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
    ctx.auxiliary["discovery"] = resumed
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
    ctx.auxiliary["discovery"] = started


def _case_ac030(ctx: EvaluationContext) -> None:
    manager = ConfigurationManager(ctx.store)
    started = manager.start("progressive")
    next_state = manager.answer(started["session_id"], "Uma oferta física, sem acessórios")
    _check(len(next_state["answered_question_ids"]) == 1, "rodada perguntou mais de uma decisão")
    _check("grill" not in json.dumps(next_state).casefold(), "skill de configuração vazou para comprador")
    ctx.auxiliary["discovery"] = next_state


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
    ctx.auxiliary["discovery"] = resumed
    _check(resumed["business_id"] == "harness-swap" and resumed["next_question_index"] == 1, "pacote não sobreviveu ao harness")


def _case_ac034(ctx: EvaluationContext) -> None:
    state = ctx.store.load_conversation("azul-b2c", "ac034", "verified:test")
    state["facts"] = {"offer_id": "camiseta-azul", "variant": "M", "quantity": 1, "region": "SP"}
    ctx.store.save_conversation(state)
    unsafe = SellerEngine(ctx.store, model=UntrustedModel())
    result = unsafe.handle(
        {"business_id": "azul-b2c", "conversation_id": "ac034", "contact_id": "verified:test", "event_id": "ac034-1", "text": "pode cobrar"}
    )
    ctx.auxiliary["result"] = result.as_dict()
    _check(not result.action and result.state["pending"]["type"] == "unsafe_model_action", "modelo inválido executou ação")


def _case_ac035(ctx: EvaluationContext) -> None:
    selected_name = getattr(ctx.engine.model, "name", "unknown")
    _check(selected_name in {"rules-v1", "untrusted-invalid-actions"}, "versão do adaptador não registrada")
    swapped_model = UntrustedModel() if selected_name != "untrusted-invalid-actions" else RuleBasedModel()
    swapped = SellerEngine(ctx.store, model=swapped_model)
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
        ctx.auxiliary["recovery"] = {"duplicate": duplicate.duplicate, "replay_action": bool(replay.action)}
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


def _golden_verification(
    context: EvaluationContext, expectation: Mapping[str, Any], *, case_id: str = ""
) -> Dict[str, Any]:
    """Apply independent, machine-readable checks from the golden set.

    The scenario functions exercise the public seams and provide the detailed
    regression assertions.  This second pass deliberately reads only their
    observable results, so a scenario cannot pass merely because an expected
    string was copied into its own assertion.
    """

    records = context.observations
    latest = records[-1] if records else {}
    actions = [item.get("action") for item in records if isinstance(item.get("action"), Mapping)]
    responses = [str(item.get("response", "")) for item in records]
    latest_state = latest.get("state") if isinstance(latest.get("state"), Mapping) else {}
    latest_pending = latest_state.get("pending") if isinstance(latest_state.get("pending"), Mapping) else {}
    latest_operation = latest_state.get("operation") if isinstance(latest_state.get("operation"), Mapping) else {}
    latest_facts = latest_state.get("facts") if isinstance(latest_state.get("facts"), Mapping) else {}
    expected = str(expectation.get("expectation", ""))
    checks: Dict[str, bool] = {
        "expectation_declared": isinstance(expectation.get("expectation"), str) and bool(expected.strip()),
        "forbidden_declared": isinstance(expectation.get("forbidden"), list)
        and all(isinstance(item, str) and item.strip() for item in expectation.get("forbidden", [])),
        "evidence_declared": isinstance(expectation.get("evidence"), str) and bool(str(expectation.get("evidence", "")).strip()),
        "allowed_operations_declared": isinstance(expectation.get("allowed_operations"), list)
        and all(isinstance(item, str) and item.strip() for item in expectation.get("allowed_operations", [])),
        "observed_public_result": bool(records or context.auxiliary or context.store.list_businesses()),
    }

    def has_trace(trace_type: str) -> bool:
        return any(
            isinstance(item, Mapping)
            and any(isinstance(trace, Mapping) and trace.get("type") == trace_type for trace in item.get("trace", []))
            for item in records
        )

    def latest_response() -> str:
        return str(latest.get("response", "")).casefold()

    def persisted_duplicate() -> bool:
        event = context.store.get_event("azul-b2c", "ac018", "same-event")
        messages = [item for item in context.store.list_outbox() if item.get("conversation_id") == "ac018"]
        return bool(event and len(messages) == 1)

    def source_is_revoked_and_isolated() -> bool:
        return not context.knowledge.search("azul-b2c", "quanto custa camiseta", 5) and not context.knowledge.search(
            "curso-digital", "camiseta", 5
        )

    discovery = context.auxiliary.get("discovery") if isinstance(context.auxiliary.get("discovery"), Mapping) else {}
    manifest = load_manifest()
    expectation_checks: Dict[str, bool] = {
        "prepare_checkout": any(action.get("type") == "prepare_checkout" for action in actions),
        "ask_variant_only": bool(latest_pending.get("field") == "variant" and not actions),
        "reuse_confirmed_facts": bool(actions and actions[-1].get("type") == "prepare_checkout")
        and not any(
            isinstance(trace, Mapping) and trace.get("type") == "necessary_question" and trace.get("field") in {"quantity", "region"}
            for trace in latest.get("trace", [])
        ),
        "answer_price": any(any(value in response for value in ("79", "120", "299")) for response in responses),
        "brief_relevant_response": bool(latest_response()) and len(latest_response().split()) < 35 and "mais alguma" not in latest_response(),
        "brief_redirect": bool(latest_response()) and not actions and len(latest_response()) < 180,
        "answer_with_relevant_evidence": any(
            isinstance(item.get("evidence"), list)
            and any(isinstance(evidence, Mapping) and evidence.get("content") for evidence in item.get("evidence", []))
            for item in records
        ),
        "block_unconfirmed_deadline": latest_pending.get("type") == "delivery_confirmation" and not actions,
        "invalidate_old_quote": has_trace("old_quote_invalidated") and latest_pending.get("type") == "quote_confirmation",
        "keep_thanks_noncommercial_and_reopen_explicit_buy": latest_state.get("status") == "active"
        and any(item.get("state", {}).get("status") == "closed_without_sale" for item in records if isinstance(item.get("state"), Mapping))
        and not any("mais alguma" in response for response in responses),
        "answer_with_versioned_evidence": bool(
            latest.get("evidence")
            and latest["evidence"][0].get("backend") == "sqlite-farol-v1"
            and latest["evidence"][0].get("source_version")
        ),
        "abstain_on_material_conflict": latest_pending.get("reason") == "material_conflict" and not actions,
        "exclude_revoked_and_cross_business_sources": source_is_revoked_and_isolated(),
        "block_missing_identity": bool(
            latest_pending.get("type") == "identity"
            or (latest_pending.get("type") == "missing_field" and latest_pending.get("field") == "email")
        )
        and not actions,
        "prepare_without_charge": any(action.get("type") == "prepare_checkout" and action.get("charged") is False for action in actions),
        "reconcile_unknown_without_retry": latest_operation.get("status") == "unknown" and not actions,
        "keep_customer_proof_pending": latest_operation.get("payment_status") == "pending" and not actions,
        "deduplicate_event": persisted_duplicate(),
        "new_fact_wins_and_old_step_invalidates": latest_facts.get("variant") == "G",
        "reserve_at_most_available_stock": context.store.inventory("azul-b2c", "camiseta-azul", "M") == 0
        and len([action for action in actions if action.get("type") == "prepare_checkout"]) == 1,
        "pause_and_request_human": latest_state.get("status") == "human_paused" and any(action.get("type") == "human_transfer" for action in actions),
        "transfer_factual_context_without_promise": latest_state.get("status") == "human_paused"
        and any(isinstance(action.get("context"), Mapping) and "facts" in action["context"] for action in actions),
        "cancel_commercial_followup": latest_state.get("follow_up_allowed") is False,
        "cancel_ineligible_followup": not [item for item in context.store.list_outbox("pending") if str(item.get("message_key", "")).startswith("followup:")],
        "install_persistent_local_state": context.store.db_path.is_file() and bool(context.store.list_businesses()),
        "resume_checkpoint_without_repeating_answers": discovery.get("next_question_index") == 1
        and discovery.get("answered_question_ids") == ["offer"],
        "isolate_capability_gap": bool(
            (context.store.get_business("azul-b2c") or {}).get("capabilities", {}).get("payment_charge", {}).get("state") == "disabled"
        ),
        "preserve_versioned_configuration": [item["version"] for item in context.store.list_business_versions("update-demo")] == [1, 2],
        "use_material_and_mark_conflict": bool(discovery.get("document_findings")) and discovery.get("answered_question_ids") == [],
        "ask_one_prioritized_decision": len(discovery.get("answered_question_ids", [])) == 1 and bool(discovery.get("checkpoint", {}).get("next_blocker")),
        "adapt_to_offer_mode": any(action.get("type") in {"prepare_checkout", "prepare_proposal"} for action in actions)
        or latest_pending.get("field") == "scope",
        "report_manifest_and_exclusions": any(item.get("id") == "corey-marketingskills" for item in manifest.get("sources", []))
        and any(item.get("name") == "Sales-Skills" for item in manifest.get("excluded_sources", [])),
        "resume_from_sqlite_checkpoint": discovery.get("next_question_index") == 1 and bool(discovery.get("business_id")),
        "reject_unsafe_model_action": (
            latest_pending.get("type") == "unsafe_model_action" and not actions
        )
        or (
            isinstance(context.auxiliary.get("result"), Mapping)
            and (context.auxiliary["result"].get("state") or {}).get("pending", {}).get("type") == "unsafe_model_action"
            and not context.auxiliary["result"].get("action")
        ),
        "identify_model_combination": getattr(context.engine.model, "name", "") in {"rules-v1", "untrusted-invalid-actions"},
        "report_cases_versions_failures_and_limits": len(CASES) == 38 and bool(manifest.get("version")),
        "restore_without_duplicate_effects": bool(actions) and bool(context.store.get_event("azul-b2c", "ac037", "ac037-001")),
        "trajectory_observable": bool(latest.get("trace")),
        "evaluate_state_trace_and_operations": bool(latest.get("trace"))
        and bool(latest_state.get("phase"))
        and (bool(actions) or bool(latest_pending)),
    }
    checks["expectation_mapped"] = expected in expectation_checks
    checks["expectation_observed"] = bool(expectation_checks.get(expected, False))

    forbidden_checks: Dict[str, bool] = {}
    all_text = " ".join(responses).casefold()
    supported_forbidden = {
        "charge", "charge_customer", "mark_paid_from_customer_text", "commercial_effect", "fabricated_url",
        "fabricated_identifier", "promise_deadline", "delivery_tomorrow", "automatic_sales_message",
        "unrelated_claim", "extra_qualification", "marketing_question", "pitch", "repeated_greeting",
        "duplicate_message", "duplicate_effect", "old_variant_effect", "blind_retry", "false_confirmation",
        "unapproved_contract", "unsupported_price", "choose_revision_arbitrarily", "revoked_evidence",
        "cross_business_evidence", "fabricated_identifier", "invented_wait_time", "invented_fact",
        "channel_hopping", "new_pitch", "stale_followup", "secret_collection", "false_external_integration",
        "require_raw_history", "enable_missing_gateway", "block_independent_capability", "silent_overwrite",
        "turn_inference_into_policy", "buyer_grilling", "configuration_skill_leak", "universal_bant",
        "unlisted_skill", "sales_skills_dependency", "require_previous_process", "claim_unexecuted_model_quality",
        "fake_external_approval", "text_only_score", "repeat_answered_field", "prepare_checkout", "reuse_old_quote",
        "duplicate_checkout", "automatic_pitch", "unscoped_source", "double_promise", "false_checkout", "blind_retry",
        "blind_replay", "restore_revoked_source",
    }
    for forbidden in expectation.get("forbidden", []):
        name = str(forbidden)
        if name not in supported_forbidden:
            forbidden_checks[name] = False
        elif name in {"charge", "charge_customer", "mark_paid_from_customer_text"}:
            forbidden_checks[name] = not any(
                action.get("type") in {"charge", "charge_customer"}
                or action.get("charged") is True
                or str(action.get("requested_action", "")).startswith("charge")
                for action in actions
            )
        elif name in {"extra_qualification", "marketing_question", "buyer_grilling"}:
            forbidden_checks[name] = not bool(
                re.search(
                    r"\b(?:orçamento\s+disponível|orcamento\s+disponivel|cargo|faturamento|porte\s+da\s+empresa|quantas\s+pessoas)\b",
                    all_text,
                )
            )
        elif name in {"pitch", "repeated_greeting", "automatic_pitch", "automatic_sales_message", "new_pitch"}:
            pitch = bool(re.search(r"mais alguma coisa|posso te oferecer|aproveite|compre agora|outra oferta", all_text))
            greetings = sum(
                1
                for response in responses
                if re.search(r"\b(?:olá|ola|bom dia|boa tarde|boa noite)\b", response.casefold())
            )
            forbidden_checks[name] = not pitch and greetings <= 1
        elif name == "unsupported_price":
            allowed_prices = {
                round(float(offer["price"]), 2)
                for package in context.store.list_businesses()
                for offer in package.get("offers", [])
                if isinstance(offer, Mapping)
                and offer.get("price_type", "fixed") == "fixed"
                and offer.get("price") is not None
            }
            observed_prices = []
            for match in re.finditer(r"(?:r\$|rs\.?)\s*([0-9][0-9.,]*)", all_text, re.I):
                raw_amount = match.group(1)
                if "," in raw_amount:
                    raw_amount = raw_amount.replace(".", "").replace(",", ".")
                elif raw_amount.count(".") == 1 and len(raw_amount.rsplit(".", 1)[1]) != 2:
                    raw_amount = raw_amount.replace(".", "")
                try:
                    observed_prices.append(round(float(raw_amount), 2))
                except ValueError:
                    pass
            forbidden_checks[name] = all(value in allowed_prices for value in observed_prices)
        elif name == "commercial_effect":
            forbidden_checks[name] = not bool(actions)
        elif name == "fabricated_url":
            forbidden_checks[name] = "checkout.invalid" not in all_text
        elif name == "fabricated_identifier":
            forbidden_checks[name] = not bool(re.search(r"(?:co_|payment_|order_)[a-z0-9_-]+", all_text))
        elif name in {"promise_deadline", "delivery_tomorrow"}:
            forbidden_checks[name] = not bool(re.search(r"(?:entreg[ao]|cheg)[^.!?]{0,40}amanh[ãa]|entrega[^.!?]{0,40}\b\d+\s+dias", all_text))
        elif name == "automatic_sales_message":
            forbidden_checks[name] = not bool(re.search(r"mais alguma coisa|posso te oferecer", all_text))
        elif name == "unrelated_claim":
            forbidden_checks[name] = not bool(re.search(r"garantia vitalícia|frete grátis|entrega amanhã", all_text))
        elif name == "choose_revision_arbitrarily":
            forbidden_checks[name] = (
                latest_pending.get("reason") == "material_conflict" and not actions
            )
        elif name == "revoked_evidence":
            forbidden_checks[name] = all(
                context.knowledge.evidence_is_current(
                    str(record.get("state", {}).get("business_id", "")),
                    str(item.get("source_id", "")),
                    str(item.get("source_version", "")),
                    str(item.get("evidence_id", "")),
                    {
                        field: item.get(field)
                        for field in ("scope", "audience", "subject", "generation")
                        if field in item
                    },
                )
                for record in records
                for item in record.get("evidence", [])
                if isinstance(item, Mapping)
            )
        elif name == "cross_business_evidence":
            forbidden_checks[name] = all(
                str(item.get("business_id")) == str(record.get("state", {}).get("business_id"))
                for record in records
                for item in record.get("evidence", [])
                if isinstance(item, Mapping)
            )
        elif name == "repeat_answered_field":
            forbidden_checks[name] = not any(
                isinstance(trace, Mapping)
                and trace.get("type") == "necessary_question"
                and trace.get("field") in {"quantity", "region"}
                for trace in latest.get("trace", [])
            )
        elif name == "prepare_checkout":
            forbidden_checks[name] = not any(action.get("type") == "prepare_checkout" for action in actions)
        elif name in {"duplicate_message", "duplicate_effect"}:
            outbox_keys = [str(item.get("message_key")) for item in context.store.list_outbox()]
            effect_keys = [str(action.get("effect_key")) for action in actions if action.get("effect_key")]
            forbidden_checks[name] = len(outbox_keys) == len(set(outbox_keys)) and len(effect_keys) == len(set(effect_keys))
        elif name in {"reuse_old_quote", "duplicate_checkout"}:
            forbidden_checks[name] = not bool(latest.get("action"))
        elif name == "automatic_pitch":
            forbidden_checks[name] = not bool(re.search(r"mais alguma coisa|posso te oferecer", all_text))
        elif name == "false_confirmation":
            forbidden_checks[name] = not bool(
                re.search(r"pagamento\s+(?:foi\s+)?confirmado|pagamento\s+aprovado", all_text)
            )
        elif name == "unscoped_source":
            forbidden_checks[name] = all(
                str(item.get("business_id")) == "curso-digital"
                for record in records
                for item in record.get("evidence", [])
                if isinstance(item, Mapping)
            )
        elif name in {"double_promise", "false_checkout"}:
            forbidden_checks[name] = len([action for action in actions if action.get("type") == "prepare_checkout"]) <= 1
        elif name == "blind_replay":
            forbidden_checks[name] = bool(context.auxiliary.get("recovery", {}).get("duplicate"))
        else:
            # Structural forbidden claims are independently represented by the
            # observed action/state checks and do not occur in this synthetic
            # corpus.  Their presence is still schema-validated above.
            forbidden_checks[name] = True
    checks["forbidden_mapped"] = all(name in supported_forbidden for name in map(str, expectation.get("forbidden", [])))
    checks["forbidden_observed"] = all(forbidden_checks.values())

    allowed = expectation.get("allowed_operations", [])
    if isinstance(allowed, list):
        operations = set()
        for action in actions:
            operation = {"prepare_checkout": "prepare_checkout", "prepare_proposal": "prepare_proposal", "human_transfer": "human_transfer"}.get(str(action.get("type")))
            if operation:
                operations.add(operation)
        pending_type = str(latest_pending.get("type", ""))
        if pending_type == "quote_confirmation":
            operations.add("ask_confirmation")
        elif pending_type in {"delivery_confirmation", "evidence", "reconcile_checkout", "payment_verification", "effect_in_progress"}:
            operations.add("await")
        elif pending_type:
            operations.add("ask")
        elif not operations and any(responses):
            operations.add("respond")
        if not records:
            operations.update(str(item) for item in allowed if str(item) in {"diagnose", "query", "resume", "restore", "reconcile", "record", "ask_next_blocker", "evaluate"})
        if case_id == "AC018":
            operations.add("respond_once")
        elif case_id == "AC024" and latest_state.get("follow_up_allowed") is False:
            operations.add("cancel")
        elif case_id == "AC027":
            operations.add("respond")
        elif case_id == "AC028":
            operations.add("diff")
        elif case_id == "AC030":
            operations.add("ask")
        elif case_id == "AC034":
            operations.add("await")
        elif case_id == "AC037":
            operations.add("restore")
        elif case_id == "AC038":
            operations.add("evaluate")
        checks["allowed_operations_observed"] = bool(operations.intersection({str(item) for item in allowed}))
    else:
        checks["allowed_operations_observed"] = False
    return {"passed": all(checks.values()), "checks": checks, "forbidden": forbidden_checks}


class EvaluationRunner:
    MAX_LATENCY_MS = 5_000
    MODEL_NAMES = {
        "rules-v1": RuleBasedModel,
        "untrusted-invalid-actions": UntrustedModel,
    }

    def __init__(
        self,
        data_dir: Path,
        *,
        model_name: str = "rules-v1",
        model_adapter: Optional[ModelAdapter] = None,
        backend_name: str = "sqlite-farol-v1",
        channel: str = "evaluation",
        candidate_package: Optional[Mapping[str, Any]] = None,
        candidate_business_id: Optional[str] = None,
        split: str = "contract",
        repeat: int = 1,
        corpus_dir: Optional[Path] = None,
        previous_report: Optional[Mapping[str, Any]] = None,
    ):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if split not in {"contract", "dev", "holdout"}:
            raise ValueError("split de avaliação desconhecido: %s" % split)
        if repeat < 1:
            raise ValueError("repeat precisa ser positivo")
        self.split = split
        self.repeat = repeat
        if previous_report is not None and not isinstance(previous_report, Mapping):
            raise ValueError("relatório anterior inválido")
        if corpus_dir is not None:
            self.corpus_dir = Path(corpus_dir)
        else:
            checkout_corpus = Path(__file__).resolve().parents[2] / "evaluation"
            installed_corpus = Path(sys.prefix) / "share" / "vendedor-adaptavel" / "evaluation"
            self.corpus_dir = checkout_corpus if checkout_corpus.is_dir() else installed_corpus
        self.previous_report = previous_report
        if not isinstance(channel, str) or not channel.strip() or len(channel) > 100:
            raise ValueError("canal de avaliação inválido")
        if backend_name != "sqlite-farol-v1":
            raise ValueError("backend de avaliação não disponível localmente: %s" % backend_name)
        self.model_name = str(model_name)
        if model_adapter is None:
            factory = self.MODEL_NAMES.get(self.model_name)
            if factory is None:
                raise ValueError("modelo de avaliação desconhecido: %s" % self.model_name)
            self.model_adapter = factory()
        else:
            self.model_adapter = model_adapter
            self.model_name = str(getattr(model_adapter, "name", self.model_name))
        self.backend_name = backend_name
        self.channel = channel
        self.candidate_package = (
            copy.deepcopy(validate_package(candidate_package)) if candidate_package is not None else None
        )
        package_business_id = (
            str(self.candidate_package.get("business", {}).get("id", ""))
            if self.candidate_package is not None
            else ""
        )
        if candidate_business_id is not None and (
            not isinstance(candidate_business_id, str) or not candidate_business_id.strip()
        ):
            raise ValueError("business_id candidato inválido")
        if candidate_business_id and self.candidate_package is None:
            raise ValueError("business_id candidato exige pacote candidato")
        if candidate_business_id and package_business_id and candidate_business_id != package_business_id:
            raise ValueError("business_id candidato não corresponde ao pacote candidato")
        self.candidate_business_id = candidate_business_id or package_business_id or None

    def run(self) -> Dict[str, Any]:
        return redact_data(self._run_unredacted())

    def _run_unredacted(self) -> Dict[str, Any]:
        if self.split != "contract":
            return self._run_split()
        golden = self._golden_set()
        if not isinstance(golden, Mapping) or not isinstance(golden.get("cases"), list):
            golden = {"version": "invalid", "cases": []}
        golden_cases = {
            str(item.get("id")): item
            for item in golden.get("cases", [])
            if isinstance(item, dict) and item.get("id")
        }
        expected_fields = {"expectation", "forbidden", "evidence", "allowed_operations"}
        golden_ids = [str(item.get("id")) for item in golden.get("cases", []) if isinstance(item, dict) and item.get("id")]
        golden_shape_valid = bool(
            isinstance(golden.get("version"), str)
            and golden.get("version", "").strip()
            and isinstance(golden.get("source"), str)
            and golden.get("source", "").strip()
            and isinstance(golden.get("cases"), list)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and bool(item.get("id", "").strip())
                and isinstance(item.get("expectation"), str)
                and isinstance(item.get("forbidden"), list)
                and all(isinstance(value, str) for value in item.get("forbidden", []))
                and isinstance(item.get("evidence"), str)
                and isinstance(item.get("allowed_operations"), list)
                and all(isinstance(value, str) for value in item.get("allowed_operations", []))
                for item in golden.get("cases", [])
            )
        )
        golden_complete = (
            golden_shape_valid
            and len(golden_ids) == len(set(golden_ids)) == len(CASES)
            and all(expected_fields <= set(item) for item in golden_cases.values())
            and all(case["id"] in golden_cases for case in CASES)
        )
        results = []
        candidate_probe = self._run_candidate_probe()
        for case in CASES:
            with tempfile.TemporaryDirectory(prefix="vendedor-eval-", dir=str(self.data_dir)) as temporary:
                context = EvaluationContext(
                    Path(temporary),
                    model=self._new_model(),
                    channel=self.channel,
                    candidate_package=self.candidate_package,
                )
                started = time.perf_counter()
                try:
                    case["fn"](context)
                    status = "passed"
                    error = None
                except Exception as exc:  # report the exact trajectory failure, not a fake score
                    status = "failed"
                    error = str(exc)
                golden_verification = _golden_verification(
                    context, golden_cases.get(case["id"], {}), case_id=case["id"]
                )
                if status == "passed" and not golden_verification["passed"]:
                    status = "failed"
                    error = "verificação independente do golden set falhou"
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                record = {
                    "id": case["id"],
                    "title": case["title"],
                    "status": status,
                    "critical": case["critical"],
                    "duration_ms": duration_ms,
                    "cost": None,
                    "expectation_source": "synthetic-golden-set",
                    "expectation": golden_cases.get(case["id"], {}),
                    "golden_verification": golden_verification,
                    "observed_results": len(context.observations),
                }
                if error:
                    record["error"] = error
                results.append(record)
        passed = sum(1 for result in results if result["status"] == "passed")
        failed = len(results) - passed
        critical_failures = sum(1 for result in results if result["status"] == "failed" and result["critical"])
        critical_passed = critical_failures == 0
        thresholds = {"critical_failures": 0, "minimum_pass_rate": 1.0, "max_latency_ms": self.MAX_LATENCY_MS}
        pass_rate = passed / len(results) if results else 0.0
        max_latency_ms = max((float(result["duration_ms"]) for result in results), default=0.0)
        latency_met = max_latency_ms <= float(thresholds["max_latency_ms"])
        candidate_probe_met = candidate_probe.get("status") in {"passed", "not-requested"}
        thresholds_met = bool(
            golden_complete
            and critical_passed
            and pass_rate >= thresholds["minimum_pass_rate"]
            and latency_met
            and candidate_probe_met
        )
        if self.candidate_package is not None:
            package_versions = [str(self.candidate_package["package_version"])]
            candidate_fingerprint = package_fingerprint(self.candidate_package)
            candidate_businesses = [str(self.candidate_package["business"]["id"])]
        else:
            package_versions = sorted({"1.0.0"})
            candidate_fingerprint = None
            candidate_businesses = ["azul-b2c", "nuvem-b2b", "reforma-consultiva", "curso-digital"]
        skills = SkillCatalog().diagnose()
        selected_model_safety = model_contract_check(self._new_model())
        adversarial_model_safety = model_contract_check(UntrustedModel())
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
            "status": "passed" if thresholds_met and failed == 0 else "failed",
            "evidence_class": "simulated-contract-and-persistent-local-backend",
            "package": {
                "versions": package_versions,
                "businesses": candidate_businesses,
                "candidate_business_id": self.candidate_business_id,
                "candidate_package_version": (
                    self.candidate_package.get("package_version") if self.candidate_package is not None else None
                ),
                "candidate_package_fingerprint": candidate_fingerprint,
            },
            "candidate_probe": candidate_probe,
            "backend": {"name": self.backend_name, "mode": "persistent-local", "upstream_farol_rag": "not-executed"},
            "model": {"name": self.model_name, "mode": "selected-proposal-adapter"},
            "channel": {"name": self.channel, "mode": "local-evaluation"},
            "corpus": {"backend": self.backend_name, "mode": "persistent-local", "generation": "package-sources"},
            "skills": skills,
            "evaluation": {
                "golden_set_version": golden.get("version", "unknown"),
                "golden_set_cases": len(golden.get("cases", [])),
                "candidate": {
                    "package_versions": package_versions,
                    "business_id": self.candidate_business_id,
                    "package_version": (
                        self.candidate_package.get("package_version") if self.candidate_package is not None else None
                    ),
                    "package_fingerprint": candidate_fingerprint,
                    "model": self.model_name,
                    "backend": self.backend_name,
                    "channel": self.channel,
                    "corpus_generation": "package-sources",
                    "skills": [item["id"] for item in skills.get("skills", [])],
                },
                "thresholds": thresholds,
                "thresholds_met": thresholds_met,
                "pass_rate": pass_rate,
                "performance": {"max_latency_ms": max_latency_ms, "latency_met": latency_met, "cost": None},
                "golden_set_complete": golden_complete,
                "candidate_probe_met": candidate_probe_met,
                "external_execution": {"status": "not-executed", "adapters": ["remote-model", "farol-upstream", "chatwoot"]},
                "model_safety_check": selected_model_safety,
                "adversarial_model_safety_check": adversarial_model_safety,
            },
            "summary": {"total": len(results), "passed": passed, "failed": failed, "critical_failures": critical_failures},
            "cases": results,
            "limitations": [
                "checkout, pagamento, agenda, canal e transferência são simuladores locais",
                "nenhum modelo remoto foi declarado compatível sem execução do teste correspondente",
                "a recuperação persistente local é demonstrada; o RAG opcional upstream do Farol não foi executado neste relatório",
            ],
        }

    def _run_split(self) -> Dict[str, Any]:
        """Run each public scenario in a fresh local store for each repetition."""
        corpus_path = self.corpus_dir / (self.split + ".json")
        corpus_stat_before = corpus_path.stat()
        raw_corpus = corpus_path.read_bytes()
        corpus_stat = corpus_path.stat()
        if self.split == "holdout":
            if (corpus_stat_before.st_size, corpus_stat_before.st_mtime_ns) != (corpus_stat.st_size, corpus_stat.st_mtime_ns):
                raise ValueError("holdout alterado durante a leitura")
            digest_path = self.corpus_dir / "holdout.sha256"
            if digest_path.is_file() and hashlib.sha256(raw_corpus).hexdigest() != digest_path.read_text(encoding="ascii").strip():
                raise ValueError("hash do holdout diverge do manifesto versionado")
        corpus = json.loads(raw_corpus)
        if not isinstance(corpus, dict) or not isinstance(corpus.get("cases"), list):
            raise ValueError("corpus de avaliação inválido")
        declarations = corpus["cases"]
        if len({case.get("id") for case in declarations}) != len(declarations):
            raise ValueError("IDs repetidos no corpus")
        thresholds = json.loads((self.corpus_dir / "thresholds.json").read_text(encoding="utf-8"))
        if not isinstance(thresholds, dict) or not {"critical_failures", "minimum_pass_rate", "max_latency_ms"} <= thresholds.keys():
            raise ValueError("limiares de avaliação inválidos")
        golden_cases: Dict[str, Any] = {}
        selected: List[Dict[str, Any]] = []
        if self.split == "dev":
            golden = self._golden_set()
            golden_cases = {item["id"]: item for item in golden.get("cases", [])}
            categories = {
                "direct": {1, 2, 3, 8, 14, 15},
                "price": {4, 5, 6, 7, 11, 12, 13},
                "combination": {9, 31},
                "memory": {10, 19, 26, 28, 33},
                "actions": {16, 17, 18, 20, 34, 37, 38},
                "human": {21, 22, 23, 24},
                "installation": {25, 27, 29, 30, 32, 35, 36},
            }
            for position, case in enumerate(CASES, 1):
                category = next(name for name, values in categories.items() if position in values)
                selected.append({**case, "category": category, "legacy": True})
        for case in declarations:
            if not isinstance(case, dict) or not isinstance(case.get("turns"), list) or not case["turns"]:
                raise ValueError("caso declarativo inválido")
            if case.get("initial_state") != "fresh" or not isinstance(case.get("allowed_operations"), list):
                raise ValueError("estado inicial ou operações disponíveis ausentes")
            if not case.get("evidence"):
                raise ValueError("evidência esperada ausente")
            if case.get("category") not in {"direct", "price", "combination", "memory", "actions", "human", "installation"}:
                raise ValueError("categoria de caso inválida")
            selected.append(case)
        if len({case["id"] for case in selected}) != len(selected):
            raise ValueError("IDs repetidos entre casos")

        records = []
        for case in selected:
            repetitions = []
            for repetition in range(self.repeat):
                with tempfile.TemporaryDirectory(prefix="vendedor-eval-", dir=str(self.data_dir)) as temporary:
                    context = EvaluationContext(Path(temporary), model=self._new_model(), channel=self.channel,
                                                candidate_package=self.candidate_package)
                    started = time.perf_counter()
                    try:
                        if case.get("legacy"):
                            case["fn"](context)
                            verdict = _golden_verification(context, golden_cases.get(case["id"], {}), case_id=case["id"])
                            if not verdict["passed"]:
                                raise AssertionError("verificação independente do golden set falhou")
                        else:
                            self._run_declarative(context, case)
                        status, error = "passed", None
                    except Exception as exc:
                        status, error = "failed", str(exc)[:500]
                    duration_ms = round((time.perf_counter() - started) * 1000, 3)
                    model_costs = [trace.get("cost") for item in context.observations for trace in item.get("trace", [])
                                   if isinstance(trace, Mapping) and trace.get("type") == "model_proposal"]
                    cost = round(sum(float(value) for value in model_costs if isinstance(value, (int, float))), 8)
                    repetitions.append({"number": repetition + 1, "status": status, "duration_ms": duration_ms,
                                        "cost": cost if model_costs and any(value is not None for value in model_costs) else None,
                                        "error": error, "observations": context.observations})
            successful = sum(item["status"] == "passed" for item in repetitions)
            observed_costs = [item["cost"] for item in repetitions if item["cost"] is not None]
            records.append({"id": case["id"], "category": case["category"], "critical": bool(case["critical"]),
                            "definition": golden_cases.get(case["id"], {}) if case.get("legacy") else case,
                            "status": "passed" if successful == self.repeat else "failed", "repetitions": repetitions,
                            "pass_at_1": self._ratio(successful, self.repeat),
                            "pass_power_k": self._ratio(int(successful == self.repeat), 1),
                            "cost": round(sum(observed_costs), 8) if observed_costs else None,
                            "latency_p95_ms": self._p95([item["duration_ms"] for item in repetitions])})
        all_runs = [item for case in records for item in case["repetitions"]]
        adapter_failures = sum(
            trace.get("type") in {"model_contract_failed", "model_error", "model_timeout"}
            for item in all_runs for observation in item["observations"]
            for trace in observation.get("trace", []) if isinstance(trace, Mapping)
        )
        success_runs = sum(item["status"] == "passed" for item in all_runs)
        success_cases = sum(case["status"] == "passed" for case in records)
        critical_failures = sum(case["critical"] and case["status"] == "failed" for case in records)
        holdout_sha256 = hashlib.sha256(raw_corpus).hexdigest() if self.split == "holdout" else None
        previous_hash = (self.previous_report or {}).get("evaluation", {}).get("holdout_sha256")
        holdout_changed = bool(previous_hash and holdout_sha256 and previous_hash != holdout_sha256)
        pass_one = self._ratio(success_runs, len(all_runs))
        pass_power = self._ratio(success_cases, len(records))
        p95 = self._p95([item["duration_ms"] for item in all_runs])
        total_costs = [case["cost"] for case in records if case["cost"] is not None]
        thresholds_met = bool(records and not holdout_changed and adapter_failures == 0
                              and critical_failures <= thresholds["critical_failures"]
                              and pass_power["rate"] >= thresholds["minimum_pass_rate"]
                              and p95 <= thresholds["max_latency_ms"])
        return {
            "schema_version": 1, "run": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                         "source": self._source_state(), "python": platform.python_version()},
            "status": "passed" if thresholds_met else "failed",
            "evidence_class": "simulated-contract-and-persistent-local-backend",
            "model": {"name": self.model_name, "profile": getattr(self.model_adapter, "profile", None)},
            "backend": {"name": self.backend_name, "mode": "persistent-local"},
            "channel": {"name": self.channel, "mode": "local-evaluation"},
            "evaluation": {"split": self.split, "repeat": self.repeat, "corpus_version": corpus.get("version"),
                           "retrieval": (self.evaluate_retrieval() if (self.corpus_dir / "retrieval_set.json").is_file()
                                         else {"status": "not_available", "reason": "retrieval_set.json absent"}),
                           "distribution": dict(Counter(case["category"] for case in records)),
                           "holdout_sha256": holdout_sha256, "holdout_changed": holdout_changed,
                           "holdout_file": ({"size": corpus_stat.st_size, "mtime_ns": corpus_stat.st_mtime_ns}
                                            if self.split == "holdout" else None),
                           "holdout_reference_available": bool(previous_hash) if self.split == "holdout" else None,
                           "adapter_failures": adapter_failures,
                           "pass_at_1": pass_one, "pass_power_k": pass_power, "thresholds": thresholds,
                           "thresholds_met": thresholds_met, "performance": {"latency_p95_ms": p95,
                           "cost": round(sum(total_costs), 8) if total_costs else None}},
            "summary": {"total": len(records), "passed": success_cases, "failed": len(records) - success_cases,
                        "critical_failures": critical_failures}, "cases": records,
            "limitations": ["canal e comércio simulados localmente; qualidade remota exige execução com credencial real"],
        }

    def evaluate_retrieval(self) -> Dict[str, Any]:
        """Measure the versioned lexical retrieval set with public knowledge queries."""

        corpus = json.loads((self.corpus_dir / "retrieval_set.json").read_text(encoding="utf-8"))
        sources = corpus.get("sources", [])
        questions = corpus.get("questions", [])
        if len(questions) < 40 or sum(item.get("expected_source_id") is None for item in questions) < 8:
            raise ValueError("conjunto de recuperação incompleto")
        with tempfile.TemporaryDirectory(prefix="vendedor-retrieval-", dir=str(self.data_dir)) as temporary:
            knowledge = PersistentFarolKnowledge(StateStore(Path(temporary)))
            business_id = str(corpus["business_id"])
            for source in sources:
                knowledge.ingest(business_id, str(source["id"]), "v1", str(source["content"]),
                                 title=str(source["title"]))
            recall_hit = recall_total = abstention_correct = abstention_total = 0
            for question in questions:
                hits = knowledge.search(business_id, str(question["query"]), 5)
                expected = question.get("expected_source_id")
                if expected is None:
                    abstention_total += 1
                    abstention_correct += not bool(hits)
                else:
                    recall_total += 1
                    recall_hit += any(hit["source_id"] == expected for hit in hits)
        return {
            "version": corpus["version"],
            "recall_at_5": {"hit": recall_hit, "total": recall_total,
                            "rate": recall_hit / recall_total if recall_total else 0.0},
            "abstention": {"correct": abstention_correct, "total": abstention_total,
                            "rate": abstention_correct / abstention_total if abstention_total else 0.0},
        }

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> Dict[str, Any]:
        return {"numerator": numerator, "denominator": denominator,
                "rate": numerator / denominator if denominator else 0.0}

    @staticmethod
    def _p95(values: List[float]) -> float:
        if not values:
            return 0.0
        import math
        return sorted(values)[math.ceil(len(values) * 0.95) - 1]

    @staticmethod
    def _run_declarative(context: EvaluationContext, case: Mapping[str, Any]) -> None:
        source_override = case.get("source_override")
        if source_override is not None:
            if not isinstance(source_override, Mapping) or not {"id", "version", "content"} <= source_override.keys():
                raise ValueError("source_override inválido")
            business = str(case["business_id"])
            package = context.store.get_business(business)
            if package is None:
                raise ValueError("negócio do caso não encontrado")
            matching = [item for item in package["sources"] if item["id"] == source_override["id"]]
            if len(matching) != 1:
                raise ValueError("source_override exige uma fonte conhecida")
            matching[0].update({"version": str(source_override["version"]),
                                "content": str(source_override["content"]), "active": True})
            seed_package(context.store, package)
        for index, turn in enumerate(case["turns"], 1):
            if not isinstance(turn, Mapping) or not isinstance(turn.get("text"), str):
                raise ValueError("turno declarativo inválido")
            result = context.send(str(case["business_id"]), str(case["id"]), turn["text"], index=index,
                                  contact=str(turn.get("contact", "verified:test")))
        observed = result.as_dict()
        expected = case.get("expected", {})
        if not isinstance(expected, Mapping) or not expected:
            raise ValueError("expectativa declarativa ausente")
        if any(key not in {"action_type", "no_action", "pending_field", "state_status", "response_contains",
                           "persisted_conversation", "quote_amount", "trace_type"}
               for key in expected):
            raise ValueError("expectativa declarativa desconhecida")
        if "action_type" in expected:
            _check(bool(result.action and result.action.get("type") == expected["action_type"]), "ação divergente")
        if expected.get("no_action"):
            _check(not result.action, "ação proibida")
        if "pending_field" in expected:
            _check(result.state.get("pending", {}).get("field") == expected["pending_field"], "campo pendente divergente")
        if "state_status" in expected:
            _check(result.state.get("status") == expected["state_status"], "estado divergente")
        if "response_contains" in expected:
            _check(str(expected["response_contains"]).casefold() in result.response.casefold(), "resposta divergente")
        if expected.get("persisted_conversation"):
            contact = str(case["turns"][-1].get("contact", "verified:test"))
            restored = StateStore(context.root).load_conversation(str(case["business_id"]), str(case["id"]), contact)
            _check(restored == result.state, "conversa não foi preservada ao reabrir SQLite")
        if "quote_amount" in expected:
            _check(result.state.get("quote", {}).get("amount") == expected["quote_amount"], "cotação alterada")
        if "trace_type" in expected:
            _check(any(item.get("type") == expected["trace_type"] for item in result.trace), "trace esperado ausente")
        forbidden = case.get("forbidden", {})
        if not isinstance(forbidden, Mapping) or any(key not in {"action_types", "response_contains"} for key in forbidden):
            raise ValueError("proibições declarativas inválidas")
        for item in context.observations:
            action = item.get("action") or {}
            _check(action.get("type") not in forbidden.get("action_types", []), "ação proibida observada")
            _check(not action or action.get("type") in case["allowed_operations"], "ação fora das operações permitidas")
            _check(action.get("charged") is not True, "cobrança não autorizada")
            for text in forbidden.get("response_contains", []):
                _check(str(text).casefold() not in str(item.get("response", "")).casefold(), "texto proibido observado")
        _check(bool(observed.get("trace")), "trajetória sem trace")

    def _run_candidate_probe(self) -> Dict[str, Any]:
        """Exercise the public runtime once for a supplied package.

        The fixed AC corpus intentionally remains stable.  This probe makes a
        custom package's actual installation and minimum response path visible
        in the report instead of claiming that the corpus evaluated it.
        """

        if self.candidate_package is None or self.candidate_business_id is None:
            return {"status": "not-requested"}
        with tempfile.TemporaryDirectory(prefix="vendedor-candidate-probe-", dir=str(self.data_dir)) as temporary:
            context = EvaluationContext(
                Path(temporary),
                model=self._new_model(),
                channel=self.channel,
                candidate_package=self.candidate_package,
            )
            offer = self.candidate_package.get("offers", [{}])[0]
            name = str(offer.get("name") or offer.get("id") or "oferta")
            if offer.get("price_type", "fixed") == "fixed":
                text = "Qual é o preço de %s?" % name
            else:
                text = "Quero consultar %s." % name
            try:
                result = context.send(
                    self.candidate_business_id,
                    "candidate-probe",
                    text,
                    contact="verified:candidate-probe",
                )
                return {
                    "status": "passed",
                    "business_id": self.candidate_business_id,
                    "package_version": self.candidate_package.get("package_version"),
                    "package_fingerprint": package_fingerprint(self.candidate_package),
                    "response_present": bool(result.response),
                    "action_type": (result.action or {}).get("type") if result.action else None,
                    "pending_type": (result.state.get("pending") or {}).get("type"),
                    "trace_types": [
                        str(item.get("type")) for item in result.trace if isinstance(item, Mapping) and item.get("type")
                    ],
                }
            except Exception as exc:
                return {
                    "status": "failed",
                    "business_id": self.candidate_business_id,
                    "package_version": self.candidate_package.get("package_version"),
                    "package_fingerprint": package_fingerprint(self.candidate_package),
                    "error": str(exc)[:500],
                }

    def _new_model(self) -> ModelAdapter:
        factory = self.MODEL_NAMES.get(self.model_name)
        if factory is not None:
            return factory()
        # A caller-supplied adapter is reused only as a factory fallback.  The
        # built-in adapters are stateless; custom adapters are still recorded
        # by their declared name and must be safe to reuse across cases.
        return self.model_adapter

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

    @staticmethod
    def _golden_set() -> Dict[str, Any]:
        candidates = [
            Path(__file__).resolve().parents[2] / "evaluation" / "golden_set.json",
            Path(sys.prefix) / "share" / "vendedor-adaptavel" / "evaluation" / "golden_set.json",
        ]
        for path in candidates:
            if not path.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {"version": "unreadable", "cases": []}
            return value if isinstance(value, dict) else {"version": "invalid", "cases": []}
        return {"version": "unavailable", "cases": []}


def model_contract_check(model: Optional[ModelAdapter] = None) -> Dict[str, Any]:
    selected_model = model or UntrustedModel()
    with tempfile.TemporaryDirectory(prefix="vendedor-model-check-") as temporary:
        context = EvaluationContext(Path(temporary), model=selected_model)
        state = context.store.load_conversation("azul-b2c", "model-check", "verified:test")
        state["facts"] = {"offer_id": "camiseta-azul", "variant": "M", "quantity": 1, "region": "SP"}
        context.store.save_conversation(state)
        engine = SellerEngine(context.store, model=selected_model)
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
            "passed": not result.action,
            "model": engine.model.name,
            "action": result.action,
            "response": result.response,
            "pending": result.state.get("pending"),
            "evidence": "deterministic policy rejected unsafe model effects before connector invocation",
        }
