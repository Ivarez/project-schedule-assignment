"""Script de experimentación y benchmark reproducible (Sección 5.4).

Genera/carga los 4 escenarios oficiales, valida la consistencia de entrada,
ejecuta los algoritmos de asignación, valida las salidas con el juez independiente
y guarda resultados en results/benchmark_results.json y results/benchmark_results.csv.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.data_manager import (
    ensure_default_scenarios,
    load_instance,
    validate_instance_consistency,
)
from src.solver import run_all_solvers

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data"
RESULTS_ROOT = PROJECT_ROOT / "results"


def main() -> None:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    paths = ensure_default_scenarios(DATA_ROOT)

    all_records = []
    json_dump = {}

    header = (
        f"{'Escenario':<20} {'|E|':>4} {'|S|':>4} {'Algoritmo':<44} "
        f"{'Válido':<7} {'Z(X)':>9} {'Asig.':>10} {'Social':>8} {'Log.(m)':>8} {'Tiempo(ms)':>10}"
    )
    print("=" * len(header))
    print("  BENCHMARK EXPERIMENTAL · ASIGNACIÓN DE HORARIOS ESTUDIANTILES (PUJ)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for key, folder in paths.items():
        inst = load_instance(folder)
        ok, errs = validate_instance_consistency(inst)
        if not ok:
            raise RuntimeError(f"Error de consistencia en {key}: {errs}")

        include_exact = len(inst.students) <= 10
        results = run_all_solvers(inst, include_exact=include_exact, exact_time_limit=3.0)
        json_dump[key] = {
            "stats": {
                "students": len(inst.students),
                "courses": len(inst.courses),
                "sections": len(inst.sections),
                "social_links": len(inst.social_links),
                "seed": inst.seed,
            },
            "results": {k: v.to_dict() for k, v in results.items()},
        }

        for algo_key, res in results.items():
            ev = res.evaluation
            asig_str = f"{ev.assigned_count}/{ev.requested_count}"
            soc_str = f"{ev.social_matches}/{ev.total_social_links}"
            valid_str = "SÍ" if ev.valid else f"NO({len(ev.violations)})"
            print(
                f"{key:<20} {len(inst.students):>4} {len(inst.sections):>4} "
                f"{res.algorithm:<44} {valid_str:<7} {ev.z_score:>9.2f} "
                f"{asig_str:>10} {soc_str:>8} {ev.raw_logistics:>8.1f} {res.runtime_ms:>10.2f}"
            )
            all_records.append({
                "scenario": key,
                "students": len(inst.students),
                "courses": len(inst.courses),
                "sections": len(inst.sections),
                "algorithm_key": algo_key,
                "algorithm": res.algorithm,
                "valid": ev.valid,
                "violations": len(ev.violations),
                "z_score": round(ev.z_score, 4),
                "assigned": ev.assigned_count,
                "requested": ev.requested_count,
                "assignment_rate": round(ev.assignment_rate, 4),
                "social_matches": ev.social_matches,
                "social_total": ev.total_social_links,
                "raw_logistics": round(ev.raw_logistics, 4),
                "runtime_ms": round(res.runtime_ms, 3),
                "optimal": res.metadata.get("optimal", False),
            })
        print("-" * len(header))

    with (RESULTS_ROOT / "benchmark_results.json").open("w", encoding="utf-8") as f:
        json.dump(json_dump, f, ensure_ascii=False, indent=2)

    if all_records:
        with (RESULTS_ROOT / "benchmark_results.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_records[0].keys()))
            writer.writeheader()
            writer.writerows(all_records)

    print(f"Resultados guardados en: {RESULTS_ROOT}")


if __name__ == "__main__":
    main()
