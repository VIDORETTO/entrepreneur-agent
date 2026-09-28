from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sales_agent.clock import FixedClock
from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.storage import StateStore


def pytest_addoption(parser):
    parser.addoption("--clock-shift-days", type=int, default=0, help="Shift the process clock for date-independent tests")


@pytest.fixture(autouse=True, scope="session")
def shifted_process_clock(request):
    days = request.config.getoption("--clock-shift-days")
    if days:
        import time_machine

        with time_machine.travel(datetime.now(timezone.utc) + timedelta(days=days), tick=True):
            yield
    else:
        yield


@pytest.fixture
def clock():
    return FixedClock("2026-09-20T12:00:00+00:00")


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
