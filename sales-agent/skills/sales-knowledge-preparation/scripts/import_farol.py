"""Import a generated Farol artifact through the public local adapter."""

import argparse
import json

from sales_agent.knowledge import FarolArtifactImporter, PersistentFarolKnowledge
from sales_agent.storage import StateStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=".vendedor-data")
    parser.add_argument("--business-id", required=True)
    parser.add_argument("path")
    args = parser.parse_args()
    store = StateStore(args.data_dir)
    count = FarolArtifactImporter(PersistentFarolKnowledge(store)).import_package(args.business_id, args.path)
    print(json.dumps({"imported_documents": count, "backend": "farol-artifact-v1"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
