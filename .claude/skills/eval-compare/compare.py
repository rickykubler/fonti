"""Compare two `fonti eval run` JSON reports: metric deltas and differing settings."""

import json
import sys
from pathlib import Path
from typing import Any

# Metrics where a lower value is better; every other metric is higher-is-better.
LOWER_IS_BETTER = {"false_refusals"}


def load(path: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def lower_is_better(metric: str) -> bool:
    return metric in LOWER_IS_BETTER or metric.endswith("_s")


def flatten(settings: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in settings.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}."))
        else:
            flat[name] = value
    return flat


def main(baseline_path: str, candidate_path: str) -> None:
    baseline, candidate = load(baseline_path), load(candidate_path)
    if baseline["dataset"] != candidate["dataset"]:
        print(f"WARNING: different datasets ({baseline['dataset']} vs {candidate['dataset']})")

    print(f"| Metric | {baseline['label']} | {candidate['label']} | Delta | |")
    print("|---|---|---|---|---|")
    before, after = baseline["summary"], candidate["summary"]
    for metric in sorted(before.keys() | after.keys()):
        old, new = before.get(metric), after.get(metric)
        if old is None or new is None:
            print(f"| {metric} | {old} | {new} | n/a | |")
            continue
        delta = new - old
        worse = delta > 0 if lower_is_better(metric) else delta < 0
        flag = "REGRESSION" if worse and abs(delta) > 1e-9 else ""
        print(f"| {metric} | {old:.4f} | {new:.4f} | {delta:+.4f} | {flag} |")

    old_settings, new_settings = flatten(baseline["settings"]), flatten(candidate["settings"])
    changed = [
        f"- {key}: {old_settings.get(key)} -> {new_settings.get(key)}"
        for key in sorted(old_settings.keys() | new_settings.keys())
        if old_settings.get(key) != new_settings.get(key)
    ]
    print("\nSettings that differ:" if changed else "\nSettings are identical.")
    print("\n".join(changed))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: compare.py <baseline.json> <candidate.json>")
    main(sys.argv[1], sys.argv[2])
