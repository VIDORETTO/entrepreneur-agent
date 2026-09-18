"""Model adapters and the deterministic Portuguese proposal interpreter."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Mapping, Optional, Protocol

from .types import Proposal


class ModelAdapter(Protocol):
    name: str

    def propose(self, text: str, package: Mapping[str, Any], state: Mapping[str, Any]) -> Proposal: ...


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

        if re.search(r"comprovante|comprovado|paguei|pagamento realizado|pix enviado", value):
            intent = "payment_proof"
        elif re.search(r"quanto custa|quanto sai|qual o preço|qual o preco|valor|preço|preco", value):
            intent = "price"
        elif re.search(r"característica|caracteristica|inclui|garantia|como acesso|acesso|prazo|entrega|devolução|devolucao", value):
            intent = "knowledge"
        elif re.search(r"comprar|compra|quero esse|quero a|vou levar|manda|checkout|pagamento|contratar|orçamento|orcamento|agendar", value):
            intent = "buy"
        elif facts:
            intent = "update"
        elif re.search(r"oi|olá|ola|bom dia|boa tarde|boa noite", value):
            intent = "greeting"
        else:
            intent = "unknown"

        condition = facts.get("deadline_condition")
        requested_action = "execute" if intent == "buy" else None
        return Proposal(
            intent=intent,
            offer_id=offer_id,
            facts=facts,
            condition=condition,
            requested_action=requested_action,
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
            model_name=self.name,
            confidence="invalid-contract",
            raw={"tool": "charge", "customer_id": "invented"},
        )


class HTTPModelAdapter:
    """Optional OpenAI-compatible JSON adapter; never receives secrets in logs."""

    allowed_intents = {"unknown", "stop", "human", "thanks", "payment_proof", "price", "knowledge", "buy", "update", "greeting"}

    @staticmethod
    def _endpoint_is_allowed(endpoint: str) -> bool:
        parsed = urllib.parse.urlsplit(endpoint)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        return bool((parsed.scheme == "https" or local_http) and parsed.hostname and not parsed.username and not parsed.password)

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 15,
        retries: int = 1,
        max_response_bytes: int = 1_000_000,
    ):
        if not self._endpoint_is_allowed(endpoint):
            raise ValueError("SELLER_MODEL_URL precisa usar HTTPS; HTTP só é aceito em localhost")
        if not api_key.strip() or not model.strip():
            raise ValueError("modelo remoto exige chave e nome não vazios")
        if timeout <= 0 or timeout > 120 or retries < 0 or retries > 3 or not 1024 <= max_response_bytes <= 10_000_000:
            raise ValueError("limites do adaptador HTTP são inválidos")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.max_response_bytes = max_response_bytes
        self.name = "http:%s" % model

    def _send(self, request: urllib.request.Request) -> Dict[str, Any]:
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl() if hasattr(response, "geturl") else self.endpoint
                    if not self._endpoint_is_allowed(final_url):
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
        prompt = {
            "text": text,
            "package": {"business": package.get("business"), "offers": package.get("offers")},
            "state": {"facts": state.get("facts", {}), "pending": state.get("pending")},
            "contract": "Return JSON with intent, offer_id, facts, condition, requested_action. Do not execute effects.",
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps({"model": self.model, "messages": [{"role": "user", "content": json.dumps(prompt)}]}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
            method="POST",
        )
        payload = self._send(request)
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise ValueError("modelo remoto retornou choices fora do contrato")
        message = choices[0].get("message")
        if not isinstance(message, Mapping):
            raise ValueError("modelo remoto retornou message fora do contrato")
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
        return Proposal(
            intent=intent,
            offer_id=parsed.get("offer_id"),
            facts=dict(facts),
            condition=parsed.get("condition"),
            requested_action=parsed.get("requested_action"),
            model_name=self.name,
            confidence="external-unverified",
            raw=parsed,
        )
