from pathlib import Path

import pytest

from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.storage import StateStore


@pytest.fixture
def app(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    seed_examples(store)
    return store, SellerEngine(store)


def event(business_id: str, conversation_id: str, event_id: str, text: str, contact_id: str = "verified:test"):
    return {
        "business_id": business_id,
        "conversation_id": conversation_id,
        "contact_id": contact_id,
        "channel": "test",
        "event_id": event_id,
        "text": text,
    }
