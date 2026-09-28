"""Model adapters and the deterministic Portuguese proposal interpreter."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol

from .types import Proposal


class ModelAdapter(Protocol):
    name: str

    def propose(self, text: str, package: Mapping[str, Any], state: Mapping[str, Any]) -> Proposal: ...


def load_model_config(path: str) -> Dict[str, Any]:
    """Resolve model credentials from environment without persisting their value."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("configuração do modelo precisa ser objeto JSON")
    profile = document.get("profile", "openai")
    if profile not in {"openai", "openai-compatible"}:
        raise ValueError("perfil do modelo inválido")
    reference = document.get("api_key", "env:OPENAI_API_KEY" if profile == "openai" else "")
    if not isinstance(reference, str) or not reference.startswith("env:") or not reference[4:].isidentifier():
        raise ValueError("chave do modelo exige referência env:NOME")
    token = os.environ.get(reference[4:], "")
    if not token:
        raise ValueError("variável de chave do modelo não configurada")
    model = document.get("model") or os.environ.get("SELLER_MODEL_NAME", "")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("SELLER_MODEL_NAME precisa estar configurado")
    endpoint = document.get("endpoint") or (
        "https://api.openai.com/v1/chat/completions" if profile == "openai" else ""
    )
    prices = document.get("prices", {})
    if not isinstance(prices, dict) or any(key not in {"input_per_million", "output_per_million"} for key in prices):
        raise ValueError("tabela de preços do modelo inválida")
    return {"profile": profile, "endpoint": endpoint, "api_key": token, "model": model, "prices": prices,
            "fallback": document.get("fallback", "rules")}


def normalize(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def _number(text: str, default: Optional[int] = None) -> Optional[int]:
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else default


class RuleBasedModel:
    name = "rules-v1"

    def propose(self, text: str, package: Mapping[str, Any], state: Mapping[str, Any]) -> Proposal:
        value = normalize(text)
        facts: Dict[str, Any] = {}
        offer_id = None
        for offer in package.get("offers", []):
            aliases = [offer.get("id", ""), offer.get("name", "")] + list(offer.get("aliases", []))
            if any(alias and normalize(str(alias)) in value for alias in aliases):
                offer_id = str(offer["id"])
                break
        if not offer_id:
            offer_id = state.get("facts", {}).get("offer_id")

        if re.search(r"não quero|nao quero|\bpare\b|\bparar\b|sem mais mensagens|cancelar contato|não me mande", value):
            return Proposal("stop", offer_id, model_name=self.name)
        if re.search(r"humano|atendente|pessoa|representante|falar com alguém|falar com alguem", value):
            return Proposal("human", offer_id, requested_action="transfer", model_name=self.name)
        if re.search(r"obrigad|valeu|tá bom|ta bom|ok,? obrigado", value):
            return Proposal("thanks", offer_id, model_name=self.name)

        size = re.search(r"\b(?:tamanho\s*)?(pp|p|m|g|gg|xg)\b", value)
        if size:
            facts["variant"] = size.group(1).upper()
        color = re.search(r"\b(azul|preta?|branca?|vermelh[oa]|verde)\b", value)
        if color:
            facts["color"] = color.group(1)
        quantity = re.search(r"(?:\b|\s)(\d+)\s*(?:unidades?|licenças?|licencas?|itens?|peças?|pecas?)\b", value)
        if quantity:
            facts["quantity"] = int(quantity.group(1))
        else:
            words = {"uma": 1, "um": 1, "duas": 2, "dois": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5}
            for word, amount in words.items():
                if re.search(r"\b%s\b" % word, value) and re.search(r"unidade|licença|licenca|item|peça|peca|agora são|agora sao", value):
                    facts["quantity"] = amount
                    break
        if re.search(r"pix", value):
            facts["payment_method"] = "pix"
        if re.search(r"parcel|cartão|cartao|crédito|credito", value):
            facts["payment_method"] = "installments"
        email = re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", value)
        if email:
            facts["email"] = email.group(0)
        if re.search(r"são paulo|sao paulo|sp\b", value):
            facts["region"] = "SP"
        if re.search(r"rio de janeiro|\brj\b", value):
            facts["region"] = "RJ"
        if re.search(r"empresa\s+([\wÀ-ÿ -]+)", value):
            facts["company_name"] = re.search(r"empresa\s+([\wÀ-ÿ -]+)", value).group(1).strip()
        if re.search(r"reforma completa|completa", value):
            facts["scope"] = "reforma completa"
        elif re.search(r"revestimento|revestimentos", value):
            facts["scope"] = "troca de revestimentos"
        if re.search(r"cozinha|sala|banheiro", value):
            facts["site"] = "cozinha" if "cozinha" in value else ("sala" if "sala" in value else "banheiro")
        if re.search(r"sexta|amanhã|amanha|prazo|chegar", value):
            facts["deadline_condition"] = value
        if re.search(r"confirmo|pode seguir|pode mandar|manda o link|fechar|finalizar", value):
            facts["confirmation"] = True

        preference_match = re.search(r"\bprefiro\s+(.{1,200})", value)
        preference_signal = bool(preference_match)
        if preference_match:
            facts["preference"] = preference_match.group(1).strip(" .!?;")
        objection_signal = bool(
            re.search(
                r"\b(?:caro|cara|barato|desconto|vou pensar|vale a pena|não tenho certeza|nao tenho certeza|"
                r"não sei se|nao sei se|difícil|dificil|insegur[oa])\b",
                value,
            )
        )

        if re.search(r"comprovante|comprovado|paguei|pagamento realizado|pix enviado", value):
            intent = "payment_proof"

        if re.search(r"pedido não chegou|pedido nao chegou|não recebi|nao recebi|pós-venda|pos-venda|suporte|problema com", value):
            intent = "post_sale"
        if re.search(r"financeiro|cobrança|cobranca|fatura|nota fiscal|estorno|reembolso", value):
            intent = "financial"
        topics = []
        if re.search(r"garantia", value):
            topics.append("guarantee")
        if re.search(r"troca", value):
            topics.append("exchange")
        if re.search(r"devolução|devolucao|reembolso", value):
            topics.append("return")
        if re.search(r"quanto custa|quanto sai|qual o preço|qual o preco|valor|preço|preco", value):
            topics.append("price")
        elif re.search(r"\b(?:caro|cara|barato|desconto)\b", value):
            topics.append("price")
        if re.search(r"acesso|duração|duracao|liberação|liberacao|meses", value):
            topics.append("access")
        if re.search(r"prazo|entrega|chegar|envio", value):
            topics.append("delivery")
        if re.search(r"pagamento|pix|cartão|cartao|parcel", value):
            topics.append("payment")
        if re.search(r"estoque|disponível|disponivel|tamanho", value):
            topics.append("availability")
        purchase_signal = bool(
            re.search(
                r"comprar|compra|quero esse|quero a|vou levar|manda(?:r)? o link|checkout|contratar|"
                r"orçamento|orcamento|agendar|fechar|finalizar",
                value,
            )
        )
        question_signal = bool(
            re.search(
                r"\?|\bquanto(?: custa| sai)?\b|\bqual(?: é| e)?\b|\bcomo funciona\b|\bpor quanto tempo\b|"
                r"\btem como\b|\bquais?\b",
                value,
            )
        )
        financial_signal = bool(re.search(r"financeiro|cobrança|cobranca|fatura|nota fiscal|estorno|reembolso", value))
        if financial_signal:
            intent = "financial"
        elif preference_signal:
            intent = "preference"
        elif objection_signal:
            intent = "objection"
        elif purchase_signal and not (question_signal and not re.search(r"quero|vou|comprar|contratar|manda", value)):
            # A ready buyer can mention variant, payment or delivery while
            # still asking for the commercial operation. Those words do not
            # turn a purchase into a knowledge lookup.
            intent = "buy"
        elif facts and (
            state.get("pending")
            or state.get("quote")
            or state.get("operation", {}).get("type") == "checkout"
        ) and not question_signal:
            # A terse correction such as "agora são duas licenças" continues
            # the existing operation and is handled by the policy engine.
            intent = "update"
        elif len(topics) > 1:
            intent = "knowledge"
        elif topics == ["price"]:
            intent = "price"
        elif topics:
            intent = "knowledge"
        elif purchase_signal:
            intent = "buy"
        elif facts:
            intent = "update"
        elif re.search(r"oi|olá|ola|bom dia|boa tarde|boa noite", value):
            intent = "greeting"
        else:
            intent = "unknown"

        if re.search(r"comprovante|comprovado|paguei|pagamento realizado|pix enviado", value):
            intent = "payment_proof"
        if re.search(r"pedido não chegou|pedido nao chegou|não recebi|nao recebi|pós-venda|pos-venda|suporte|problema com", value):
            intent = "post_sale"

        condition = facts.get("deadline_condition")
        requested_action = "execute" if intent == "buy" else None
        return Proposal(
            intent=intent,
            offer_id=offer_id,
            facts=facts,
            condition=condition,
            requested_action=requested_action,
            topics=topics,
            model_name=self.name,
            raw={"text": text},
        )


class UntrustedModel:
    """Adversarial adapter used to prove the motor does not trust action text."""

    name = "untrusted-invalid-actions"

    def propose(self, text: str, package: Mapping[str, Any], state: Mapping[str, Any]) -> Proposal:
        return Proposal(
            intent="buy",
            offer_id=state.get("facts", {}).get("offer_id") or package.get("offers", [{}])[0].get("id"),
            facts={"quantity": 1},
            requested_action="charge_customer_with_fabricated_id",
            topics=[],
            model_name=self.name,
            confidence="invalid-contract",
            raw={"tool": "charge", "customer_id": "invented"},
        )


class HTTPModelAdapter:
    """Optional OpenAI-compatible JSON adapter; never receives secrets in logs."""

    allowed_intents = {"unknown", "stop", "human", "thanks", "payment_proof", "financial", "price", "knowledge", "buy", "update", "greeting", "post_sale", "support", "objection", "preference"}
    fact_fields = (
        "color", "company_name", "confirmation", "deadline_condition", "email",
        "payment_method", "preference", "quantity", "region", "scope", "site", "variant",
    )
    proposal_schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": sorted(allowed_intents)},
            "offer_id": {"type": ["string", "null"]},
            "facts": {
                "type": "object",
                "properties": {key: {"type": ["string", "integer", "boolean", "null"]} for key in fact_fields},
                "required": list(fact_fields),
                "additionalProperties": False,
            },
            "condition": {"type": ["string", "null"]},
            "requested_action": {"type": ["string", "null"]},
            "topics": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["intent", "offer_id", "facts", "condition", "requested_action", "topics"],
        "additionalProperties": False,
    }

    @staticmethod
    def _endpoint_is_allowed(endpoint: str) -> bool:
        parsed = urllib.parse.urlsplit(endpoint)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        return bool((parsed.scheme == "https" or local_http) and parsed.hostname and not parsed.username and not parsed.password)

    @staticmethod
    def _same_origin(left: str, right: str) -> bool:
        first, second = urllib.parse.urlsplit(left), urllib.parse.urlsplit(right)
        return (first.scheme, first.hostname, first.port) == (second.scheme, second.hostname, second.port)

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 15,
        retries: int = 1,
        max_response_bytes: int = 1_000_000,
        profile: str = "openai",
        fallback: Optional[str] = None,
        prices: Optional[Mapping[str, float]] = None,
    ):
        if not self._endpoint_is_allowed(endpoint):
            raise ValueError("SELLER_MODEL_URL precisa usar HTTPS; HTTP só é aceito em localhost")
        if not api_key.strip() or not model.strip():
            raise ValueError("modelo remoto exige chave e nome não vazios")
        if timeout <= 0 or timeout > 120 or retries < 0 or retries > 3 or not 1024 <= max_response_bytes <= 10_000_000:
            raise ValueError("limites do adaptador HTTP são inválidos")
        if profile not in {"openai", "openai-compatible"} or fallback not in {None, "rules", "assist"}:
            raise ValueError("perfil ou fallback do modelo inválido")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.max_response_bytes = max_response_bytes
        self.name = "http:%s" % model
        self.profile = profile
        self.fallback = fallback
        self.prices = dict(prices or {})
        if any(not isinstance(value, (int, float)) or value < 0 for value in self.prices.values()):
            raise ValueError("preços do modelo inválidos")

    def _send(self, request: urllib.request.Request) -> Dict[str, Any]:
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl() if hasattr(response, "geturl") else self.endpoint
                    if not self._endpoint_is_allowed(final_url) or not self._same_origin(final_url, self.endpoint):
                        raise ValueError("redirecionamento do modelo usa endpoint inseguro")
                    body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise ValueError("resposta do modelo excedeu o limite permitido")
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("modelo remoto retornou envelope inválido")
                return payload
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or exc.code >= 500
                if not retryable or attempt >= self.retries:
                    raise ValueError("modelo remoto recusou a solicitação (HTTP %d)" % exc.code) from None
            except urllib.error.URLError:
                if attempt >= self.retries:
                    raise ValueError("modelo remoto está indisponível") from None
            if attempt < self.retries:
                time.sleep(0.1 * (2**attempt))
        raise ValueError("modelo remoto está indisponível")

    def propose(self, text: str, package: Mapping[str, Any], state: Mapping[str, Any]) -> Proposal:
        system = json.dumps(
            {
                "contract": "Interpret buyer data into a proposal only. Never execute effects. Return intent, offer_id, facts, condition, requested_action, topics.",
                "package": {"business": package.get("business"), "offers": package.get("offers")},
                "state": {"facts": state.get("facts", {}), "pending": state.get("pending")},
                "buyer_skill_context": package.get("_buyer_skill_context", []),
            },
            ensure_ascii=False,
        )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": "<buyer_message>%s</buyer_message>" % text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "seller_proposal", "strict": True, "schema": self.proposal_schema},
            },
        }
        if self.profile == "openai-compatible":
            body["response_format"]["json_schema"].pop("strict")
        total_calls = 0
        last_error = ""
        started = time.monotonic()
        for attempt in range(2 if self.fallback else 1):
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            request.add_unredirected_header("Authorization", "Bearer " + self.api_key)
            total_calls += 1
            try:
                payload = self._send(request)
                proposal = self._parse_proposal(payload)
                proposal.raw["model_calls"] = total_calls
                proposal.raw["profile"] = self.profile
                proposal.raw["latency_ms"] = round((time.monotonic() - started) * 1000, 3)
                usage = payload.get("usage")
                if isinstance(usage, Mapping):
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (prompt_tokens, completion_tokens)):
                        proposal.raw["usage"] = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
                        proposal.raw["cost"] = round(
                            (prompt_tokens * self.prices.get("input_per_million", 0)
                             + completion_tokens * self.prices.get("output_per_million", 0)) / 1_000_000,
                            9,
                        )
                return proposal
            except ValueError as exc:
                last_error = str(exc)
                if attempt == 0 and self.fallback:
                    body["messages"].append({"role": "system", "content": "Repair proposal JSON: %s" % last_error})
                    continue
                if not self.fallback:
                    raise
        fallback = RuleBasedModel().propose(text, package, state) if self.fallback == "rules" else Proposal(intent="unknown")
        fallback.raw.update({"model_contract_failed": True, "model_calls": total_calls, "profile": self.profile,
                             "latency_ms": round((time.monotonic() - started) * 1000, 3)})
        if "indisponível" in last_error or "timeout" in last_error.casefold():
            fallback.raw["model_timeout"] = True
        return fallback

    def _parse_proposal(self, payload: Mapping[str, Any]) -> Proposal:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise ValueError("modelo remoto retornou choices fora do contrato")
        message = choices[0].get("message")
        if not isinstance(message, Mapping):
            raise ValueError("modelo remoto retornou message fora do contrato")
        if message.get("refusal"):
            raise ValueError("modelo remoto recusou a proposta")
        content = message.get("content", "{}")
        parsed = json.loads(content) if isinstance(content, str) else content
        if not isinstance(parsed, dict):
            raise ValueError("modelo remoto não retornou objeto JSON")
        intent = parsed.get("intent", "unknown")
        if not isinstance(intent, str) or intent not in self.allowed_intents:
            raise ValueError("modelo remoto retornou intent fora do contrato")
        facts = parsed.get("facts", {})
        if not isinstance(facts, Mapping) or len(facts) > 32 or not all(isinstance(key, str) for key in facts):
            raise ValueError("modelo remoto retornou facts fora do contrato")
        for field in ("offer_id", "condition", "requested_action"):
            if parsed.get(field) is not None and not isinstance(parsed[field], str):
                raise ValueError("modelo remoto retornou %s fora do contrato" % field)
        topics = parsed.get("topics", [])
        if not isinstance(topics, list) or len(topics) > 16 or not all(isinstance(topic, str) and topic in {"guarantee", "exchange", "return", "price", "access", "delivery", "payment", "availability", "general"} for topic in topics):
            raise ValueError("modelo remoto retornou topics fora do contrato")
        return Proposal(
            intent=intent,
            offer_id=parsed.get("offer_id"),
            facts={key: value for key, value in facts.items() if value is not None},
            condition=parsed.get("condition"),
            requested_action=parsed.get("requested_action"),
            topics=list(topics),
            model_name=self.name,
            confidence="external-unverified",
            raw=parsed,
        )
