"""Business package loading, examples and resumable owner discovery."""

from __future__ import annotations

import copy
import json
import re
import tempfile
import uuid
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from .knowledge import PersistentFarolKnowledge
from .skills import SkillCatalog
from .storage import StateStore
from .validation import PackageError, validate_package


def load_manifest() -> Dict[str, Any]:
    """Load the source manifest from the repository or an installed wheel."""
    repository_manifest = Path(__file__).resolve().parents[2] / "manifest.json"
    if repository_manifest.is_file():
        return json.loads(repository_manifest.read_text(encoding="utf-8"))
    return json.loads(resources.files("sales_agent").joinpath("resources/manifest.json").read_text(encoding="utf-8"))


def _source(
    source_id: str,
    title: str,
    content: str,
    *,
    origin: str = "fictional-example",
    scope: str = "",
) -> Dict[str, Any]:
    return {
        "id": source_id,
        "version": "2026-09-17.1",
        "title": title,
        "content": content,
        "locator": "examples/%s.md" % source_id,
        "origin": origin,
        "status": "approved",
        "audience": "buyer",
        "scope": scope,
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
                "objection_policy": {
                    "discounts": "not-approved-by-default",
                    "urgency": "never-invent",
                    "conditions_source": "approved-package-and-evidence",
                },
                "preference_transitions": [
                    {
                        "id": "informational",
                        "terms": ["só receber informações", "so receber informacoes", "sem checkout"],
                        "profile": "informational",
                        "objective": "information",
                        "source": "package-policy",
                    },
                    {
                        "id": "consultative",
                        "terms": ["prefiro proposta", "prefiro orçamento", "prefiro orcamento"],
                        "profile": "consultative",
                        "objective": "proposal",
                        "source": "package-policy",
                    },
                ],
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
            {"id": "seller-conversation", "source": "project", "version": "1", "when": "always"},
        ],
        "settings": {
            "language": "pt-BR",
            "timezone": "America/Sao_Paulo",
            "model_mode": "rules-v1",
            "skill_context_budget": 8_000,
        },
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
                scope="camiseta-azul",
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
                scope="plano-padrao",
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
                scope="reforma-cozinha",
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
                scope="curso-analise",
            )
        ]
    else:
        raise PackageError("template de exemplo desconhecido: %s" % template)
    return validate_package(base)


def load_package(path: Union[Path, str]) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_package(payload)


def seed_package(store: StateStore, package: Mapping[str, Any]) -> Dict[str, Any]:
    checked = validate_package(package)
    previous = store.get_business(str(checked["business"]["id"]))
    store.save_business(dict(checked))
    PersistentFarolKnowledge(store).ingest_package_sources(
        str(checked["business"]["id"]), checked, previous_package=previous
    )
    return dict(checked)


def seed_examples(store: StateStore) -> List[Dict[str, Any]]:
    return [seed_package(store, example_package(template)) for template in ("physical", "b2b", "service", "digital")]


def promote_package(store: StateStore, package: Mapping[str, Any]) -> Dict[str, Any]:
    """Promote a reviewed draft without allowing silent in-place activation."""

    checked = validate_package(package)
    business_id = str(checked["business"]["id"])
    current = store.get_business(business_id)
    if not current:
        raise PackageError("não existe rascunho instalado para promover: %s" % business_id)
    if current.get("lifecycle") != "draft":
        raise PackageError("a versão instalada não é um rascunho")
    if checked.get("lifecycle") != "active":
        raise PackageError("pacote promovido precisa declarar lifecycle active")
    if checked.get("package_version") == current.get("package_version"):
        raise PackageError("promoção precisa alterar package_version")
    owner_configuration = checked.get("owner_configuration") or current.get("owner_configuration")
    if not isinstance(owner_configuration, Mapping) or not isinstance(owner_configuration.get("decisions"), list):
        raise PackageError("promoção exige decisões estruturadas do dono")
    decisions = owner_configuration.get("decisions") or []
    if not decisions:
        raise PackageError("promoção exige ao menos uma decisão estruturada do dono")
    for index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping):
            raise PackageError("decisão do dono inválida na posição %d" % index)
        if not all(isinstance(decision.get(field), str) and decision[field].strip() for field in ("question_id", "source")):
            raise PackageError("decisão do dono precisa de question_id e source")
        if decision.get("status") not in {"confirmed", "approved"}:
            raise PackageError("decisão do dono precisa de aprovação estruturada")
    approved_capabilities = set()
    for decision in decisions:
        values = decision.get("approved_capabilities", decision.get("capabilities", []))
        if isinstance(values, list):
            approved_capabilities.update(str(value) for value in values)
    enabled = {
        name
        for name, entry in (checked.get("capabilities") or {}).items()
        if isinstance(entry, Mapping) and entry.get("state") in {"enabled", "assisted"}
    }
    if enabled and not approved_capabilities:
        raise PackageError("capacidades habilitadas exigem aprovação estruturada")
    if enabled and not enabled.issubset(approved_capabilities):
        missing = sorted(enabled - approved_capabilities)
        raise PackageError("capacidades sem aprovação estruturada: %s" % ", ".join(missing))
    if "owner_configuration" not in checked and current.get("owner_configuration"):
        checked["owner_configuration"] = current["owner_configuration"]
    return seed_package(store, checked)


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
        capability: str = "checkout_prepare",
    ) -> Dict[str, Any]:
        if not isinstance(capability, str) or not capability.strip() or len(capability) > 100:
            raise ValueError("capability inválida")
        session_id = session_id or "discovery-%s" % uuid.uuid4().hex[:10]
        material_list = [str(item) for item in (materials or [])]
        material_text = "\n\n".join(material_list)
        findings = self._material_findings(material_text)
        payload = {
            "schema_version": 1,
            "session_id": session_id,
            "business_id": business_id,
            "template": template,
            "business_name": business_name or business_id,
            "materials": material_list,
            "capability": capability,
            "document_findings": findings,
            "facts": {},
            "fact_records": {},
            "blockers": [item["id"] for item in self._questions_for_capability(capability)],
            "decisions": [],
            "answered_question_ids": [],
            "deferred_question_ids": [],
            "questions": self._questions_for_capability(capability),
            "next_question_index": 0,
            "status": "in_progress",
            "capabilities": {"knowledge_query": "pending", "checkout_prepare": "pending"},
            "checkpoint": {"last_completed": None, "next_blocker": self._questions_for_capability(capability)[0]["id"]},
        }
        self.store.save_discovery(session_id, business_id, payload)
        return payload

    @staticmethod
    def _questions_for_capability(capability: str) -> List[Dict[str, str]]:
        order = {
            "human_transfer": ["autonomy", "next_step", "offer", "operational_truth"],
            "knowledge_query": ["operational_truth", "offer", "next_step", "autonomy"],
            "quote": ["offer", "operational_truth", "next_step", "autonomy"],
            "catalog_query": ["offer", "operational_truth", "next_step", "autonomy"],
        }.get(capability, [item["id"] for item in QUESTIONS])
        by_id = {item["id"]: item for item in QUESTIONS}
        return [copy.deepcopy(by_id[item_id]) for item_id in order]

    @staticmethod
    def _material_findings(material_text: str) -> List[Dict[str, str]]:
        value = material_text.casefold()
        findings: List[Dict[str, str]] = []
        term_patterns = {
            "preço": ("preço", "preco"),
            "checkout": ("checkout",),
            "proposta": ("proposta", "orçamento", "orcamento"),
            "prazo": ("prazo", "entrega", "chegar"),
            "estoque": ("estoque", "disponível", "disponivel"),
            "acesso": ("acesso", "liberação", "liberacao"),
        }
        amount_values = {
            re.sub(r"[^0-9]", "", match)
            for match in re.findall(r"r\$\s*([0-9]+(?:[.,][0-9]{1,2})?)", value)
        }
        for term, patterns in term_patterns.items():
            if not any(pattern in value for pattern in patterns):
                continue
            status = "inferred"
            if term == "preço" and len(amount_values) > 1:
                status = "conflicting"
            findings.append({"term": term, "status": status, "source": "owner-material"})

        question_patterns = {
            "offer": ("oferta", "produto", "serviço", "servico", "curso", "camiseta", "plano"),
            "next_step": ("checkout", "proposta", "visita", "agenda", "agendar"),
            "operational_truth": ("preço", "preco", "estoque", "acesso", "catálogo", "catalogo", "fonte"),
            "autonomy": ("cobrar", "enviar", "preparar", "consultar", "autonomia"),
        }
        for field, patterns in question_patterns.items():
            if not any(pattern in value for pattern in patterns):
                findings.append({"term": field, "status": "absent", "source": "owner-material"})
        return findings

    def status(self, session_id: str) -> Dict[str, Any]:
        value = self.store.get_discovery(session_id)
        if not value:
            raise ValueError("sessão de configuração não encontrada: %s" % session_id)
        return value

    def inspect(self, business_id: str) -> Dict[str, Any]:
        package = self.store.get_business(business_id)
        if not package:
            raise ValueError("negócio não configurado: %s" % business_id)
        versions = self.store.list_business_versions(business_id)
        declared = [item for item in package.get("skills", []) if isinstance(item, Mapping)]
        catalog = SkillCatalog()
        available = {item["id"]: item for item in catalog.list_skills()}
        skills = [
            {
                **dict(item),
                "declared": True,
                "available": str(item.get("id")) in available and available[str(item.get("id"))]["available"],
                "audience": available.get(str(item.get("id")), {}).get("audience"),
            }
            for item in declared
        ]
        return {
            "business_id": business_id,
            "package_version": package.get("package_version"),
            "lifecycle": package.get("lifecycle", "active"),
            "storage_version": versions[-1]["version"] if versions else None,
            "business": copy.deepcopy(package.get("business", {})),
            "offers": copy.deepcopy(package.get("offers", [])),
            "capabilities": copy.deepcopy(package.get("capabilities", {})),
            "sources": [
                {"id": item.get("id"), "version": item.get("version"), "status": item.get("status"), "origin": item.get("origin")}
                for item in package.get("sources", [])
            ],
            "effective_sources": self.store.list_sources(business_id),
            "versions": [
                {"storage_version": item["version"], "package_version": item["package"].get("package_version"), "lifecycle": item["package"].get("lifecycle", "active")}
                for item in versions
            ],
            "skills": skills,
            "application": {"observed": False, "reason": "inspeção não executa uma conversa"},
            "governance": {"revocation_is_runtime_state": True},
        }

    def diff(self, business_id: str, candidate: Mapping[str, Any]) -> Dict[str, Any]:
        current = self.store.get_business(business_id)
        if not current:
            raise ValueError("negócio não configurado: %s" % business_id)
        checked = validate_package(candidate)
        fields = ("package_version", "lifecycle", "business", "offers", "policies", "capabilities", "sources", "skills")
        result: Dict[str, Any] = {"business_id": business_id, "changes": [], "valid": True}
        for field in fields:
            before = self._redact(current.get(field))
            after = self._redact(checked.get(field))
            changed = before != after
            result[field] = {"changed": changed, "before": before, "after": after}
            if changed:
                result["changes"].append(field)
        return result

    def simulate(self, package: Mapping[str, Any], text: str, *, contact_id: str = "verified:simulation") -> Dict[str, Any]:
        checked = validate_package(package)
        with tempfile.TemporaryDirectory(prefix="vendedor-simulate-") as temporary:
            isolated_store = StateStore(Path(temporary))
            seed_package(isolated_store, checked)
            from .conversation import SellerEngine

            result = SellerEngine(isolated_store).handle(
                {
                    "business_id": checked["business"]["id"],
                    "conversation_id": "simulation",
                    "contact_id": contact_id,
                    "channel": "simulation",
                    "event_id": "simulation-1",
                    "text": text,
                }
            )
            return {"isolated": True, "package_version": checked["package_version"], "result": result.as_dict()}

    @staticmethod
    def _redact(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): ("<redacted>" if any(term in str(key).casefold() for term in ("secret", "token", "password", "api_key")) else ConfigurationManager._redact(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [ConfigurationManager._redact(item) for item in value]
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
            payload.setdefault("fact_records", {})[current["id"]] = {
                "value": None,
                "status": "absent",
                "source": "owner",
            }
        else:
            payload["facts"][current["id"]] = answer.strip()
            payload.setdefault("fact_records", {})[current["id"]] = {
                "value": answer.strip(),
                "status": "confirmed",
                "source": "owner",
            }
            if current["id"] in deferred:
                deferred.remove(current["id"])
        payload["decisions"].append(
            {"question_id": current["id"], "answer": answer.strip(), "status": "deferred" if deferred_answer else "confirmed", "source": "owner"}
        )
        if not deferred_answer and current["id"] not in payload["answered_question_ids"]:
            payload["answered_question_ids"].append(current["id"])
        if not question_id:
            payload["next_question_index"] = index + 1
        payload["blockers"] = [
            item["id"]
            for item in questions
            if item["id"] in deferred or item["id"] not in payload.get("answered_question_ids", [])
        ]
        payload["checkpoint"] = {
            "last_completed": current["id"] if not deferred_answer else payload.get("checkpoint", {}).get("last_completed"),
            "next_blocker": payload["blockers"][0] if payload["blockers"] else None,
        }
        if payload["next_question_index"] >= len(questions) and not deferred:
            payload["status"] = "ready"
            payload["capabilities"] = {"knowledge_query": "enabled", "checkout_prepare": "assisted"}
        else:
            payload["status"] = "in_progress"
        self.store.save_discovery(session_id, payload["business_id"], payload)
        return payload

    def restore(self, business_id: str, storage_version: int) -> Dict[str, Any]:
        """Restore a previous package as a new active promotion.

        Historical rows remain immutable.  A restore is validated and written
        as the next business version, so source revocations and the audit trail
        are preserved instead of being replaced by a file copy.
        """

        current = self.store.get_business(business_id)
        if not current:
            raise ValueError("negócio não configurado: %s" % business_id)
        historical = self.store.get_business_version(business_id, int(storage_version))
        if not historical:
            raise ValueError("versão de configuração não encontrada: %s" % storage_version)
        package = copy.deepcopy(historical["package"])
        package["lifecycle"] = "active"
        package["package_version"] = "%s-restore-%s" % (package.get("package_version", "version"), storage_version)
        package.setdefault("owner_configuration", current.get("owner_configuration"))
        package = validate_package(package)
        restored = seed_package(self.store, package)
        return {
            "restored": True,
            "business_id": business_id,
            "from_storage_version": int(storage_version),
            "package_version": restored["package_version"],
            "storage_version": self.store.list_business_versions(business_id)[-1]["version"],
            "package": restored,
        }

    def finalize(self, session_id: str) -> Dict[str, Any]:
        payload = self.status(session_id)
        if payload["status"] == "complete":
            existing = self.store.get_business(payload["business_id"])
            if not existing:
                raise ValueError("pacote finalizado não foi encontrado: %s" % payload["business_id"])
            return existing
        if payload["status"] != "ready":
            raise ValueError("configuração ainda tem pendências")
        package = example_package(payload["template"], payload["business_id"], payload["business_name"])
        offer = package["offers"][0]
        offer_name = payload["facts"].get("offer", "%s — oferta inicial" % payload["business_name"])
        offer["name"] = offer_name
        offer["aliases"] = [offer_name]
        offer["description"] = "Rascunho derivado da decisão do dono; dados operacionais ainda não aprovados."
        # Preserve the configured commercial modality.  A draft may retain
        # the shape of a direct physical/digital/B2B offer without treating
        # example prices, stock or access data as an owner approval.
        next_step = str(payload["facts"].get("next_step", "")).casefold()
        consultative = offer["kind"] == "service" or any(
            term in next_step for term in ("proposta", "orçamento", "orcamento", "consult", "visita", "agenda")
        )
        if consultative:
            offer["mode"] = "consultative"
            offer["price_type"] = "on_request"
            offer["required_fields"] = list(offer.get("consultative_questions") or ["scope"])
            offer.pop("price", None)
            offer.pop("access", None)
            if offer["kind"] == "physical":
                offer["stock"] = {}
        else:
            offer["mode"] = "direct"
            # No structured price source was approved by this checkpoint, so
            # use a variable/on-request quote while retaining direct intent.
            offer["price_type"] = "variable"
            offer.pop("price", None)
            offer.pop("access", None)
            if offer["kind"] == "physical":
                offer["stock"] = {}
        package["sources"] = []
        package["lifecycle"] = "draft"
        package["owner_configuration"] = {
            "session_id": session_id,
            "decisions": payload["decisions"],
            "document_findings": payload["document_findings"],
        }
        for name in ("catalog_query", "quote", "checkout_prepare", "human_transfer", "knowledge_query"):
            package["capabilities"][name] = {
                "state": "pending",
                "reason": "rascunho sem dados operacionais estruturados e aprovados",
            }
        package = validate_package(package)
        seed_package(self.store, package)
        payload["status"] = "complete"
        payload["capabilities"] = {name: entry["state"] for name, entry in package["capabilities"].items()}
        payload["finalized_package_version"] = package["package_version"]
        payload["finalized_storage_version"] = self.store.list_business_versions(payload["business_id"])[-1]["version"]
        self.store.save_discovery(session_id, payload["business_id"], payload)
        return package
