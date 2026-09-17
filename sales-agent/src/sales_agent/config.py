"""Business package loading, examples and resumable owner discovery."""

from __future__ import annotations

import json
import re
import uuid
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .knowledge import PersistentFarolKnowledge
from .storage import StateStore
from .validation import PackageError, validate_package


def load_manifest() -> Dict[str, Any]:
    """Load the source manifest from the repository or an installed wheel."""
    repository_manifest = Path(__file__).resolve().parents[2] / "manifest.json"
    if repository_manifest.is_file():
        return json.loads(repository_manifest.read_text(encoding="utf-8"))
    return json.loads(resources.files("sales_agent").joinpath("resources/manifest.json").read_text(encoding="utf-8"))


def _source(source_id: str, title: str, content: str, *, origin: str = "fictional-example") -> Dict[str, Any]:
    return {
        "id": source_id,
        "version": "2026-09-17.1",
        "title": title,
        "content": content,
        "locator": "examples/%s.md" % source_id,
        "origin": origin,
        "status": "approved",
    }


def example_package(template: str, business_id: Optional[str] = None, business_name: Optional[str] = None) -> Dict[str, Any]:
    """Return one of four fictional, self-contained demonstration businesses."""

    business_id = business_id or {
        "physical": "azul-b2c",
        "b2b": "nuvem-b2b",
        "service": "reforma-consultiva",
        "digital": "curso-digital",
    }.get(template, template)
    business_name = business_name or {
        "physical": "Azul & Cia (fictício)",
        "b2b": "Nuvem Clara (fictício)",
        "service": "Oficina Casa Clara (fictício)",
        "digital": "Trilha Dados (fictício)",
    }.get(template, business_id)
    base = {
        "schema_version": 1,
        "package_version": "1.0.0",
        "business": {"id": business_id, "name": business_name, "buyer_types": ["B2C"]},
        "policies": {
            "conversation": {
                "do_not_qualify_ready_buyer": True,
                "ask_only_missing_required_field": True,
                "pause_on_human_request": True,
                "stop_on_refusal": True,
            },
            "quote": {"invalidate_on": ["quantity", "payment_method", "variant", "deadline_condition"]},
            "follow_up": {"enabled": False, "respect_stop": True},
        },
        "capabilities": {
            "catalog_query": {"state": "enabled", "reason": "dados do pacote e simulador"},
            "quote": {"state": "enabled", "reason": "simulador local"},
            "checkout_prepare": {"state": "enabled", "reason": "prepara checkout sem cobrar"},
            "payment_charge": {"state": "disabled", "reason": "nenhum provedor real autorizado"},
            "human_transfer": {"state": "assisted", "reason": "fila simulada; sem equipe conectada"},
            "knowledge_query": {"state": "enabled", "reason": "backend persistente local com evidência"},
            "follow_up": {"state": "disabled", "reason": "não configurado no exemplo"},
        },
        "skills": [
            {"id": "product-marketing", "source": "corey-marketingskills", "when": "always"},
            {"id": "sales-enablement", "source": "corey-marketingskills", "when": "objection-or-material"},
            {"id": "revops", "source": "corey-marketingskills", "when": "policy-maintenance"},
            {"id": "copy-editing", "source": "corey-marketingskills", "when": "configuration"},
            {"id": "seller-conversation", "source": "project", "when": "always"},
        ],
        "settings": {"language": "pt-BR", "timezone": "America/Sao_Paulo", "model_mode": "rules-v1"},
        "sources": [],
    }
    if template == "physical":
        base["offers"] = [
            {
                "id": "camiseta-azul",
                "name": "Camiseta Azul",
                "aliases": ["camiseta azul", "camisa azul"],
                "kind": "physical",
                "mode": "direct",
                "buyer_types": ["B2C"],
                "price_type": "fixed",
                "price": 79.0,
                "currency": "BRL",
                "required_fields": ["variant", "quantity", "region"],
                "stock": {"P": 2, "M": 1, "G": 3},
                "delivery_days": 5,
                "quote_validity_minutes": 30,
                "description": "Camiseta de algodão azul, tamanhos P, M e G.",
            }
        ]
        base["sources"] = [
            _source(
                "azul-catalogo",
                "Catálogo Azul & Cia",
                "A Camiseta Azul custa R$ 79 por unidade. Há tamanhos P, M e G. A entrega simulada para SP leva 5 dias úteis. A compra direta prepara checkout, mas não cobra automaticamente.",
            )
        ]
    elif template == "b2b":
        base["business"]["buyer_types"] = ["B2B"]
        base["offers"] = [
            {
                "id": "plano-padrao",
                "name": "Plano Padrão",
                "aliases": ["plano padrão", "plano padrao", "licenças", "licencas"],
                "kind": "digital",
                "mode": "direct",
                "buyer_types": ["B2B"],
                "price_type": "fixed",
                "price": 120.0,
                "currency": "BRL",
                "required_fields": ["quantity", "company_name", "email"],
                "quote_validity_minutes": 60,
                "description": "Licença mensal do Plano Padrão por usuário.",
            }
        ]
        base["sources"] = [
            _source(
                "nuvem-plano",
                "Condições do Plano Padrão",
                "O Plano Padrão custa R$ 120 por licença por mês. Cinco licenças podem seguir para checkout. O sistema pede empresa e e-mail apenas para provisionar o acesso; cargo e orçamento não são necessários.",
            )
        ]
    elif template == "service":
        base["offers"] = [
            {
                "id": "reforma-cozinha",
                "name": "Projeto de reforma de cozinha",
                "aliases": ["reforma de cozinha", "reformar minha cozinha", "cozinha"],
                "kind": "service",
                "mode": "consultative",
                "buyer_types": ["B2C", "B2B"],
                "price_type": "on_request",
                "currency": "BRL",
                "required_fields": ["scope", "region"],
                "consultative_questions": ["scope", "region"],
                "description": "Projeto e execução sob medida, com orçamento após escopo e medidas.",
            }
        ]
        base["sources"] = [
            _source(
                "casa-escopo",
                "Política de orçamento da Oficina",
                "O valor da reforma depende do escopo e das medidas. Para preparar uma proposta, primeiro distinguir reforma completa de troca de revestimentos e confirmar a região. Não prometer preço fechado sem avaliação.",
            )
        ]
    elif template == "digital":
        base["offers"] = [
            {
                "id": "curso-analise",
                "name": "Curso de Análise de Dados",
                "aliases": ["curso de análise", "curso de analise", "curso"],
                "kind": "digital",
                "mode": "direct",
                "buyer_types": ["B2C"],
                "price_type": "fixed",
                "price": 299.0,
                "currency": "BRL",
                "required_fields": ["email"],
                "quote_validity_minutes": 30,
                "access": {"duration": "12 meses", "delivery": "liberação após pagamento confirmado"},
                "description": "Curso digital com acesso por 12 meses.",
            }
        ]
        base["sources"] = [
            _source(
                "trilha-acesso",
                "Condições de acesso do curso",
                "O Curso de Análise de Dados custa R$ 299 e dá acesso por 12 meses. A liberação ocorre após pagamento confirmado no provedor; criar checkout não significa pagamento aprovado.",
            )
        ]
    else:
        raise PackageError("template de exemplo desconhecido: %s" % template)
    return validate_package(base)


def load_package(path: Path | str) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_package(payload)


def seed_package(store: StateStore, package: Mapping[str, Any]) -> Dict[str, Any]:
    checked = validate_package(package)
    store.save_business(dict(checked))
    PersistentFarolKnowledge(store).ingest_package_sources(str(checked["business"]["id"]), checked)
    return dict(checked)


def seed_examples(store: StateStore) -> List[Dict[str, Any]]:
    return [seed_package(store, example_package(template)) for template in ("physical", "b2b", "service", "digital")]


QUESTIONS = [
    {
        "id": "offer",
        "prompt": "Qual oferta deve ser atendida primeiro e o que fica fora dela?",
        "impact": "define o primeiro escopo e evita vender uma promessa não aprovada",
    },
    {
        "id": "next_step",
        "prompt": "Quando o comprador já sabe o que quer, qual é o próximo passo correto: checkout, proposta, visita ou agenda?",
        "impact": "define avanço direto sem funil obrigatório",
    },
    {
        "id": "operational_truth",
        "prompt": "De onde vêm preço e disponibilidade, e quem mantém esses dados?",
        "impact": "separa fonte documental de dado operacional",
    },
    {
        "id": "autonomy",
        "prompt": "O que a IA pode consultar, preparar, enviar ou cobrar sozinha?",
        "impact": "define permissões; intenção não autoriza cobrança",
    },
]


class ConfigurationManager:
    """One-question-per-checkpoint owner interview."""

    def __init__(self, store: StateStore):
        self.store = store

    def start(
        self,
        business_id: str,
        *,
        template: str = "physical",
        business_name: Optional[str] = None,
        materials: Optional[Iterable[str]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session_id = session_id or "discovery-%s" % uuid.uuid4().hex[:10]
        material_text = "\n\n".join(str(item) for item in (materials or []))
        findings = []
        for term in ("preço", "preco", "checkout", "proposta", "prazo", "estoque", "acesso"):
            if term in material_text.casefold():
                findings.append({"term": term, "status": "inferred", "source": "owner-material"})
        payload = {
            "schema_version": 1,
            "session_id": session_id,
            "business_id": business_id,
            "template": template,
            "business_name": business_name or business_id,
            "materials": list(materials or []),
            "document_findings": findings,
            "facts": {},
            "decisions": [],
            "answered_question_ids": [],
            "deferred_question_ids": [],
            "questions": QUESTIONS,
            "next_question_index": 0,
            "status": "in_progress",
            "capabilities": {"knowledge_query": "pending", "checkout_prepare": "pending"},
        }
        self.store.save_discovery(session_id, business_id, payload)
        return payload

    def status(self, session_id: str) -> Dict[str, Any]:
        value = self.store.get_discovery(session_id)
        if not value:
            raise ValueError("sessão de configuração não encontrada: %s" % session_id)
        return value

    def answer(self, session_id: str, answer: str, *, question_id: Optional[str] = None) -> Dict[str, Any]:
        payload = self.status(session_id)
        if payload["status"] == "complete":
            return payload
        index = int(payload["next_question_index"])
        questions = payload["questions"]
        deferred = payload.get("deferred_question_ids", [])
        if question_id:
            current = next((item for item in questions if item["id"] == question_id), None)
        else:
            current = questions[index] if index < len(questions) else None
        if not current:
            payload["status"] = "ready" if not deferred else "in_progress"
            self.store.save_discovery(session_id, payload["business_id"], payload)
            return payload
        normalized = answer.strip().casefold()
        deferred_answer = normalized in {"não sei", "nao sei", "pular", "depois", "ainda não", "ainda nao"}
        if deferred_answer:
            if current["id"] not in deferred:
                deferred.append(current["id"])
        else:
            payload["facts"][current["id"]] = answer.strip()
            if current["id"] in deferred:
                deferred.remove(current["id"])
        payload["decisions"].append(
            {"question_id": current["id"], "answer": answer.strip(), "status": "deferred" if deferred_answer else "confirmed", "source": "owner"}
        )
        if not deferred_answer and current["id"] not in payload["answered_question_ids"]:
            payload["answered_question_ids"].append(current["id"])
        if not question_id:
            payload["next_question_index"] = index + 1
        if payload["next_question_index"] >= len(questions) and not deferred:
            payload["status"] = "ready"
            payload["capabilities"] = {"knowledge_query": "enabled", "checkout_prepare": "assisted"}
        else:
            payload["status"] = "in_progress"
        self.store.save_discovery(session_id, payload["business_id"], payload)
        return payload

    def finalize(self, session_id: str) -> Dict[str, Any]:
        payload = self.status(session_id)
        if payload["status"] not in {"ready", "complete"}:
            raise ValueError("configuração ainda tem pendências")
        package = example_package(payload["template"], payload["business_id"], payload["business_name"])
        package["owner_configuration"] = {
            "session_id": session_id,
            "decisions": payload["decisions"],
            "document_findings": payload["document_findings"],
        }
        package["capabilities"]["checkout_prepare"]["state"] = payload["capabilities"]["checkout_prepare"]
        package["capabilities"]["checkout_prepare"]["reason"] = "decisão registrada no checkpoint"
        package = validate_package(package)
        seed_package(self.store, package)
        payload["status"] = "complete"
        payload["finalized_package_version"] = 1
        self.store.save_discovery(session_id, payload["business_id"], payload)
        return package
