from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameday_lab.client import ResilientClient
from gameday_lab.factory import build_client
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import evaluate_checks, run_scenario


class UnfilteredClient(ResilientClient):
    def ladder(self, task: str) -> list[str]:
        return list(self.order)


def run_case(label, scenario, *, client_name="resilient", patch=None, unfiltered=False):
    scenarios = "configs/scenarios_cache.yaml" if scenario == "C1_faq_outage" else "configs/scenarios.yaml"
    cfg = deepcopy(load_config("configs/gameday.yaml", scenarios))
    if patch:
        patch(cfg)
    client = (UnfilteredClient(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
              if unfiltered else build_client(client_name, cfg, seed=1))
    metrics = run_scenario(cfg, scenario, client, seed=25).metrics()
    checks = evaluate_checks(metrics, cfg.scenarios[scenario].checks)
    output = {"case": label, "scenario": scenario, "seed": 25,
              "client_rng_seed": 1, "client": cfg.client, "cache": cfg.cache,
              "metrics": metrics, "checks": checks, "pass": all(checks.values())}
    path = Path("reports/experiments") / f"{label}_{scenario}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")


def broken_breaker(cfg):
    cfg.client["breaker"]["min_calls"] = 1000000000
    cfg.client["max_attempts_per_provider"] = 5


def no_budget(cfg):
    broken_breaker(cfg)
    cfg.client.update(retry_budget_ratio=100, retry_budget_max_tokens=1e9,
                      retry_budget_min_per_s=1e6)


def timeout30(cfg):
    cfg.client["attempt_timeout_s"] = 30


def cache_patch(key, value):
    def apply(cfg):
        cfg.cache[key] = value
    return apply


def main():
    for scenario in ("G2_overload_storm", "G3_brownout"):
        run_case("normal", scenario)
        run_case("broken_breaker_budget_on", scenario, patch=broken_breaker)
        run_case("broken_breaker_budget_off", scenario, patch=no_budget)
    for scenario in ("G4_slow_region", "G6_provider_outage"):
        run_case("normal", scenario)
        run_case("timeout30", scenario, patch=timeout30)
    run_case("unfiltered", "G6_provider_outage", unfiltered=True)
    run_case("without_cache", "C1_faq_outage")
    run_case("selected_cache", "C1_faq_outage", client_name="cached")
    cfg = load_config("configs/gameday.yaml", "configs/scenarios_cache.yaml")
    for threshold in sorted({0.80, cfg.cache["similarity_threshold"], 0.97}):
        run_case(f"threshold_{threshold}", "C1_faq_outage", client_name="cached",
                 patch=cache_patch("similarity_threshold", threshold))
    for ttl in (30, 60, 300):
        run_case(f"ttl_{ttl}", "C1_faq_outage", client_name="cached", patch=cache_patch("ttl_s", ttl))
    run_case("no_stale", "C1_faq_outage", client_name="cached", patch=cache_patch("max_stale_s", 0))


if __name__ == "__main__":
    main()
