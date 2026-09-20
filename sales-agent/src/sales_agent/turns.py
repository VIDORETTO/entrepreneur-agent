"""Durable debounce and turn composition for local and channel input."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional

from .conversation import SellerEngine
from .storage import StateStore, durable_key
from .types import EngineResult


class TurnAssembler:
    def __init__(self, store: StateStore, engine: SellerEngine, *, window_seconds: int = 3, max_wait_seconds: int = 15):
        if window_seconds < 0 or max_wait_seconds < window_seconds:
            raise ValueError("janela de turno inválida")
        self.store = store
        self.engine = engine
        self.window_seconds = window_seconds
        self.max_wait_seconds = max_wait_seconds

    def receive(self, event: Mapping[str, Any], *, received_at: Optional[str] = None) -> Dict[str, Any]:
        SellerEngine._validate_event(event)
        timestamp = received_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        inserted = self.store.save_inbound_message(dict(event), timestamp)
        if not inserted:
            return {"duplicate": True, "processed": False, "queued": False, "message_id": str(event["event_id"])}
        if self._urgent(str(event["text"])):
            result = self.engine.handle(dict(event))
            turn_id = durable_key("turn", str(event["business_id"]), str(event["conversation_id"]), str(event["event_id"]))
            self.store.mark_inbound_processed(
                [str(event["event_id"])], turn_id, business_id=str(event["business_id"]), conversation_id=str(event["conversation_id"])
            )
            return {"duplicate": False, "processed": True, "queued": False, "result": result, "turn_id": turn_id}
        return {"duplicate": False, "processed": False, "queued": True, "message_id": str(event["event_id"])}

    def process_due(self, *, now: Optional[str] = None) -> List[EngineResult]:
        now_value = datetime.fromisoformat((now or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00"))
        rows = self.store.list_queued_inbound()
        grouped: Dict[tuple[str, str, str], List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault((row["business_id"], row["conversation_id"], row["contact_id"]), []).append(row)
        results = []
        for (business_id, conversation_id, contact_id), messages in grouped.items():
            messages.sort(key=lambda item: (item["received_at"], int(item.get("durable_order", 0))))
            batches: List[List[Dict[str, Any]]] = []
            batch: List[Dict[str, Any]] = []
            previous_at: Optional[datetime] = None
            for message in messages:
                received = datetime.fromisoformat(message["received_at"].replace("Z", "+00:00"))
                if batch and previous_at is not None and received > previous_at + timedelta(seconds=self.window_seconds):
                    batches.append(batch)
                    batch = []
                batch.append(message)
                previous_at = received
            if batch:
                batches.append(batch)
            for messages in batches:
                first = datetime.fromisoformat(messages[0]["received_at"].replace("Z", "+00:00"))
                last = datetime.fromisoformat(messages[-1]["received_at"].replace("Z", "+00:00"))
                urgent = any(self._urgent(str(item["text"])) for item in messages)
                if (
                    not urgent
                    and now_value < last + timedelta(seconds=self.window_seconds)
                    and now_value < first + timedelta(seconds=self.max_wait_seconds)
                ):
                    continue
                message_ids = [str(item["message_id"]) for item in messages]
                event = dict(messages[0]["event"])
                turn_id = durable_key("turn", business_id, conversation_id, *message_ids)
                event["event_id"] = turn_id
                event["text"] = "\n".join(str(item["text"]) for item in messages)
                event["turn"] = {"turn_id": turn_id, "message_ids": message_ids, "received_at": [item["received_at"] for item in messages]}
                result = self.engine.handle(event)
                self.store.mark_inbound_processed(message_ids, turn_id, business_id=business_id, conversation_id=conversation_id)
                results.append(result)
        return results

    @staticmethod
    def _urgent(text: str) -> bool:
        return bool(re.search(r"humano|atendente|pessoa|representante|não quero|nao quero|pare|parar|cancelar contato", text.casefold()))
