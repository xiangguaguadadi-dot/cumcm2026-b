"""Independent pure-data review. Does not read or generate final cases or run policies."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3] / "coordinator"
REVIEW = ROOT / "experiments/20260911_stage3/final_review.py"


def main():
    namespace = runpy.run_path(str(REVIEW), run_name="independent_pure_review")
    base = []
    for mode in (3, 4):
        for group in ("g1", "g2"):
            for seed in (1, 2):
                value = 100. * seed
                base.append(dict(case_id=f"artificial-{mode}-{group}-{seed}", mode=mode, group=group,
                                 seed_cluster=seed, source_count=10, cleared_count=10, complete=True,
                                 error=None, exit_reason="user_exit", average_clear_time_s=value,
                                 total_virtual_time_s=10 * value, distance_m=500., requests=20,
                                 clear_failures=0, program_runtime_s=0.01))
    changed = [dict(r) for r in base]
    for r in changed:
        ratio = .9 if r["seed_cluster"] == 1 else .8
        r["average_clear_time_s"] *= ratio
        r["total_virtual_time_s"] *= ratio
    paired = namespace["paired"](changed, base)
    for cell in paired:
        if cell["group"] == "ALL":
            assert cell["saved_s_per_source_seed_cluster_95ci"] == [10., 40.]
            assert all(abs(x-y) < 1e-12 for x,y in zip(cell["reduction_fraction_seed_cluster_95ci"], [.1,.2]))
            assert abs(cell["delta_s_per_source"] + 25.) < 1e-12
    failures = [dict(r) for r in base]
    row = next(r for r in failures if r["mode"] == 4 and r["group"] == "g1" and r["seed_cluster"] == 1)
    row.update(complete=False, error="worker_timeout", cleared_count=None,
               average_clear_time_s=None, total_virtual_time_s=None)
    row.pop("exit_reason")
    cohort = namespace["compare_cohort"](base, [base, failures])
    for comparisons in cohort:
        for cell in comparisons:
            blocked = cell["mode"] == 4 and cell["group"] in ("ALL", "g1")
            assert cell["valid_comparison"] is not blocked
            if blocked:
                assert "candidate_mean_s_per_source" not in cell
                assert "reduction_fraction" not in cell
                assert "saved_s_per_source_seed_cluster_95ci" not in cell
    failure_cell = next(c for c in cohort[1] if c["mode"] == 4 and c["group"] == "g1")
    assert failure_cell["candidate_cleared"] is None
    assert failure_cell["observed_cleared_lower_bound"] == 10
    assert failure_cell["unknown_clearance_rows"] == 1
    rejected = {}
    for label, bad in {
        "duplicate_ids": [*base[:-1], base[0]],
        "metadata_mismatch": [dict(base[0], source_count=11), *base[1:]],
    }.items():
        try:
            namespace["paired"](bad, base)
        except AssertionError:
            rejected[label] = True
        else:
            raise AssertionError(label + " was accepted")
    reversed_cells = namespace["paired"](list(reversed(changed)), base)
    assert all(c["delta_s_per_source"] == b["delta_s_per_source"] for c,b in zip(reversed_cells,paired))
    exposed = json.loads((ROOT / "experiments/20260911_stage3/exposed_cases.json").read_text())
    shape_fixture = [c for c in exposed if c["exposure_suite"] == "v1"]
    assert len(namespace["validate_cases"](shape_fixture)) == 100
    malformed = {
        "truncated_cases": shape_fixture[:-1],
        "duplicate_case_id": [dict(shape_fixture[0], case_id=shape_fixture[1]["case_id"]), *shape_fixture[1:]],
        "wrong_cluster": [dict(shape_fixture[0], seed=shape_fixture[0]["seed"]+1), *shape_fixture[1:]],
    }
    unmixed = copy.deepcopy(shape_fixture)
    first_q4 = next(c for c in unmixed if c["mode"] == 4)
    for source in first_q4["sources"]:
        source["direction"] = None
    malformed["q4_all_omnidirectional"] = unmixed
    for label, bad in malformed.items():
        try:
            namespace["validate_cases"](bad)
        except AssertionError:
            rejected[label] = True
        else:
            raise AssertionError(label + " was accepted")
    paths = ["FINAL_VALIDATION_PLAN.md", "generate_final.py", "final_review.py",
             "audit/collect_seed_inventory.py", "audit/check_final_review.py",
             "final_candidates/combined.py", "final_candidates/R2_open_R4.py",
             "final_candidates/R3_open_R5.py"]
    sources, accesses = [], {}
    for rel in ["experiments/20260911_stage3/" + p for p in paths] + ["evaluate.py"]:
        path = ROOT / rel
        data = path.read_bytes()
        sources.append(dict(path=rel, sha256=hashlib.sha256(data).hexdigest(), lines=len(data.splitlines())))
        if path.name in ("R2_open_R4.py", "R3_open_R5.py"):
            tree = ast.parse(data)
            accesses[path.name] = sorted({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)
                and isinstance(n.value,ast.Attribute) and n.value.attr == "env"
                and isinstance(n.value.value,ast.Name) and n.value.value.id == "self"})
            assert accesses[path.name] == ["clear", "enter", "exit", "measure"]
    result = dict(status="pass", actual_environment_runs=0, new_final_data_access=False,
                  artificial_rows=8, method="Pure paired/cohort functions and source AST; no policy import or execution",
                  cohort_failure_suppression=True, unknown_clearance_preserved=True,
                  analytical_two_seed_bootstrap_bounds_correct=True, id_permutation_paired_correctly=True,
                  shape_fixture_source="2400 already-exposed v1 cases, read only; modified dictionaries are checker fixtures",
                  rejected=rejected, fixture_cohort=cohort, reviewed_sources=sources, ast_self_env_accesses=accesses)
    (HERE / "final_pipeline_review_fixtures.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("fixture_cohort", "reviewed_sources")},ensure_ascii=False))


if __name__ == "__main__":
    main()
