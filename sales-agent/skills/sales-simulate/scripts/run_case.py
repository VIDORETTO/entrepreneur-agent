"""Small portable helper for harnesses that can only execute one script."""

import json

from sales_agent.evaluation import EvaluationRunner


def main() -> int:
    report = EvaluationRunner(".vendedor-evaluation").run()
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if report["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
