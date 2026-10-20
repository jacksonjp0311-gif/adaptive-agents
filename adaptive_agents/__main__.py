import argparse
import json
from .core import Assignment, Lifecycle, Store

def main():
    parser = argparse.ArgumentParser(description="Adaptive Agents offline lifecycle demo and graph export")
    parser.add_argument("command", choices=["demo", "export"])
    parser.add_argument("--db", required=True, help="Private local SQLite path; never commit this file")
    args = parser.parse_args()
    store = Store(args.db)
    try:
        if args.command == "demo":
            lifecycle = Lifecycle(store)
            spec = lifecycle.allocate(Assignment("demo", "example", "Contract Auditor", "Inspect a synthetic contract", "Check schema fields", max_steps=1))
            instance = spec["instance_id"]
            lifecycle.transition(instance, "running")
            lifecycle.step(instance)
            lifecycle.transition(instance, "completed", summary="Synthetic demo; no external execution or verification")
            lifecycle.retire(instance, retention_ack="host-retained-fixture")
        print(json.dumps(store.graph(), indent=2))
    finally:
        store.close()

if __name__ == "__main__": main()
