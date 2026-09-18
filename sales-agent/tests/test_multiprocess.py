import multiprocessing
from pathlib import Path

from sales_agent.config import seed_examples
from sales_agent.conversation import SellerEngine
from sales_agent.storage import StateStore

from .conftest import event


def _handle_same_event(data_dir, start, results):
    store = StateStore(data_dir)
    engine = SellerEngine(store)
    start.wait()
    result = engine.handle(
        event(
            "azul-b2c",
            "multiprocess",
            "same-event",
            "Quero comprar a camiseta azul tamanho M, uma unidade para SP.",
        )
    )
    results.put({"duplicate": result.duplicate, "action": result.action})


def _reserve_last_unit(data_dir, effect_key, start, results):
    store = StateStore(data_dir)
    start.wait()
    outcome, _ = store.reserve_checkout_effect(
        effect_key,
        {"quote_id": effect_key},
        business_id="azul-b2c",
        offer_id="camiseta-azul",
        variant="M",
        quantity=1,
    )
    results.put(outcome)


def _run_pair(worker, arguments):
    context = multiprocessing.get_context("fork")
    start = context.Event()
    results = context.Queue()
    processes = [context.Process(target=worker, args=(*args, start, results)) for args in arguments]
    for process in processes:
        process.start()
    start.set()
    values = [results.get(timeout=10) for _ in processes]
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    return values


def test_duplicate_event_is_atomic_across_processes(tmp_path: Path):
    data_dir = tmp_path / "data"
    store = StateStore(data_dir)
    seed_examples(store)

    results = _run_pair(_handle_same_event, [(data_dir,), (data_dir,)])

    assert sorted(item["duplicate"] for item in results) == [False, True]
    assert all(item["action"] and item["action"]["type"] == "prepare_checkout" for item in results)
    assert len([item for item in store.list_outbox() if item["conversation_id"] == "multiprocess"]) == 1
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 0


def test_last_inventory_unit_is_atomic_across_processes(tmp_path: Path):
    data_dir = tmp_path / "data"
    store = StateStore(data_dir)
    seed_examples(store)

    outcomes = _run_pair(
        _reserve_last_unit,
        [(data_dir, "checkout:worker-1"), (data_dir, "checkout:worker-2")],
    )

    assert sorted(outcomes) == ["out_of_stock", "reserved"]
    assert store.inventory("azul-b2c", "camiseta-azul", "M") == 0
