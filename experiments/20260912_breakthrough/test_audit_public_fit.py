"""Temporary synthetic export/archive fixtures; no real data or execution.

The public feature builder is a mock so this suite checks provenance, labels,
IDs and denominators independently of feature implementation unit tests. No
worker, environment, optimizer, trainer or evaluation module is imported.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import warnings
import zipfile

import audit_public_fit as public_audit
import audit_round_archives as archive_audit


IDS = ["a"*64, "b"*64, "c"*64]
PI = "d"*64


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
    else:
        path.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")


def encode(value):
    if type(value) is dict:
        return {"@": "dict", "v": [[key, encode(item)] for key, item in sorted(value.items())]}
    if type(value) is list:
        return {"@": "list", "v": [encode(item) for item in value]}
    return value


class PublicExportFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = self.enterContext(tempfile.TemporaryDirectory(prefix="synthetic-public-audit-"))
        self.root = Path(self.temporary)
        self.campaign = self.root/"RL"/"training_round1_20260912"
        self.collection = self.campaign/"results"/"labels"
        self.dataset = self.campaign/"results"/"public"
        self.acceptance_path = self.root/"accepted_labels.json"
        self.campaign.mkdir(parents=True)
        (self.campaign/"features.py").write_text("# Synthetic feature source, never imported.\n")
        (self.campaign/"export_fit.py").write_text("# Synthetic exporter source, never imported.\n")
        self.accepted_paths = []
        self.worlds, self.public_worlds, entries = [], [], []
        for index in range(36):
            role = "fit" if index < 24 else "fit_val"
            identity = dict(world_id=f"synthetic-{index:02d}", world_sha256=f"{index+1:064x}", role=role)
            sources, exported = [], []
            count = 0 if index == 0 else 2 if index == 2 else 1
            for state_index in range(count):
                ids = [IDS[1]] if index == 1 else list(IDS)
                ref = ids.index(IDS[1])
                gains = [0. if action == IDS[1] else (i+1)/1024 for i, action in enumerate(ids)]
                origins = [f"synthetic-run-{index}-{state_index}-{i}" for i in range(len(ids))]
                events = [dict(public_world_marker=index, public_state_marker=state_index)]
                snapshot = dict(schema="synthetic-public-snapshot-v1", candidate_ids=ids, teacher_id=IDS[1],
                    features=dict(synthetic_tensor=[index, state_index]), diagnostics=dict(events_dropped=0))
                metadata = dict(choice_id=f"synthetic-choice-{index}-{state_index}", source_index=state_index+1,
                    state_index=state_index, continuation_policy_sha256=PI)
                bundle = dict(metadata, candidate_ids=ids, teacher_id=IDS[1], status="complete",
                    outcomes=[dict(action_id=action, run_id=run, paired_gain_to_A0=gain)
                              for action, run, gain in zip(ids, origins, gains)])
                handle = dict(prepared=dict(synthetic_snapshot=deepcopy(snapshot), expected_events=events),
                    token=dict(interface_public_state=encode(dict(events=events))))
                folder = self.collection/"worlds"/str(index)/str(state_index)
                bundle_path, handle_path = folder/"labels.json", folder/"handle.json.gz"
                write_json(bundle_path, bundle)
                write_json(handle_path, handle)
                self.accepted_paths.extend((bundle_path, handle_path))
                sources.append(dict(path=str(bundle_path.relative_to(self.campaign)),
                                    handle_path=str(handle_path.relative_to(self.campaign))))
                exported.append(dict(metadata, snapshot=snapshot, targets_normalized=gains, teacher_index=ref,
                    origin_run_ids=origins, reference_origin_run_id=origins[ref], complete_bundle=True))
            self.worlds.append(dict(identity, state_count=count, states=sources))
            world = dict(identity, schema="bc-rpi-round1-public-fit-world-v1", states=exported,
                state_count=count, complete=True, no_world_truth=True,
                empty_state_and_world_weight="retained with zero loss")
            self.public_worlds.append(world)
            path = self.dataset/f"{role}_w{index:03d}.json.gz"
            write_json(path, world)
            entries.append(dict(identity, path=path.name, sha256=digest_file(path), states=count))
        write_json(self.collection/"summary.json", dict(continuation_policy_sha256=PI))
        write_json(self.collection/"world_results.json", dict(worlds=self.worlds))
        self.accepted_paths.extend((self.collection/"summary.json", self.collection/"world_results.json"))
        self.manifest = dict(schema="bc-rpi-round1-public-fit-manifest-v1", worlds=entries,
            counts={"fit": 24, "fit_val": 12}, state_bundles=36, nonreference_labels=70,
            teacher_only_states=1, zero_state_worlds=1, label_scale=.002,
            continuation_policy_sha256=PI, shared_for_three_independent_initializations=True,
            trusted_exporter_sha256=digest_file(self.campaign/"export_fit.py"),
            feature_implementation_sha256=digest_file(self.campaign/"features.py"),
            source_collection_summary_sha256=digest_file(self.collection/"summary.json"),
            source_world_results_sha256=digest_file(self.collection/"world_results.json"),
            read_boundary="Synthetic public exports only")
        self.write_manifest()
        self.reseal_acceptance()
        package = ModuleType("training_round1_20260912")
        package.__path__ = []
        features = ModuleType("training_round1_20260912.features")
        def build(prepared, events):
            if events != prepared["expected_events"]:
                raise ValueError("Mock public event mapping differs")
            return deepcopy(prepared["synthetic_snapshot"])
        features.build_snapshot = Mock(side_effect=build)
        features.validate_snapshot = Mock(return_value=None)
        self.features = features
        self.enterContext(patch.dict(sys.modules, {package.__name__: package, features.__name__: features}))
        self.enterContext(patch.object(sys, "path", list(sys.path)))

    def write_manifest(self):
        write_json(self.dataset/"manifest.json", self.manifest)

    def reseal_acceptance(self):
        self.acceptance = dict(status="complete_shared_first_round_labels_verified",
            source_sha256={str(path.resolve()): digest_file(path) for path in self.accepted_paths})
        write_json(self.acceptance_path, self.acceptance)

    def write_world(self, index):
        path = self.dataset/self.manifest["worlds"][index]["path"]
        write_json(path, self.public_worlds[index])
        self.manifest["worlds"][index]["sha256"] = digest_file(path)
        self.write_manifest()

    def invoke(self):
        return public_audit.audit(self.campaign, self.collection, self.dataset, self.acceptance_path)

    def test_complete_population_retains_empty_world_teacher_only_and_nonzero_teacher_index(self):
        result = self.invoke()
        self.assertEqual(result["status"], "all_public_features_labels_and_origins_verified")
        self.assertEqual(result["counts"], dict(fit=24, fit_val=12, state_bundles=36,
            nonreference_labels=70, teacher_only_states=1, zero_state_worlds=1))
        self.assertEqual(self.features.build_snapshot.call_count, 36)
        self.assertEqual(result["actual_environment_calls"], 0)
        self.assertEqual(result["actual_optimizer_updates"], 0)

    def test_unrelated_accepted_audit_cannot_approve_this_collection(self):
        unrelated = self.collection/"unrelated.json"
        write_json(unrelated, {"synthetic": "unrelated previously audited artifact"})
        self.acceptance["source_sha256"] = {str(unrelated.resolve()): digest_file(unrelated)}
        write_json(self.acceptance_path, self.acceptance)
        with self.assertRaisesRegex(ValueError, "independently accepted label"):
            self.invoke()

    def test_each_summary_world_bundle_and_handle_must_have_accepted_path_pin(self):
        original = deepcopy(self.acceptance)
        for path in (self.collection/"summary.json", self.collection/"world_results.json",
                     self.accepted_paths[0], self.accepted_paths[1]):
            self.acceptance = deepcopy(original)
            self.acceptance["source_sha256"].pop(str(path.resolve()))
            write_json(self.acceptance_path, self.acceptance)
            with self.subTest(path=path.name), self.assertRaisesRegex(ValueError, "independently accepted label"):
                self.invoke()

    def test_accepted_label_bytes_cannot_change_after_acceptance(self):
        write_json(self.accepted_paths[0], {"changed": True})
        with self.assertRaisesRegex(ValueError, "Previously audited label artifact changed"):
            self.invoke()

    def test_same_bytes_in_an_unaccepted_collection_path_are_not_accepted_origins(self):
        other = self.campaign/"results"/"other_labels"
        other.mkdir()
        for name in ("summary.json", "world_results.json"):
            (other/name).write_bytes((self.collection/name).read_bytes())
        with self.assertRaisesRegex(ValueError, "independently accepted label"):
            public_audit.audit(self.campaign, other, self.dataset, self.acceptance_path)

    def test_features_ids_labels_teacher_and_origins_are_bound_to_accepted_handle(self):
        original = deepcopy(self.public_worlds[2])
        for field in ("features", "ids", "targets", "origins", "reference", "teacher"):
            self.public_worlds[2] = deepcopy(original)
            state = self.public_worlds[2]["states"][0]
            if field == "features":
                state["snapshot"]["features"]["synthetic_tensor"][0] += 1
            elif field == "ids":
                state["snapshot"]["candidate_ids"].reverse()
            elif field == "targets":
                state["targets_normalized"][0] += .1
            elif field == "origins":
                state["origin_run_ids"].reverse()
            elif field == "reference":
                state["reference_origin_run_id"] = state["origin_run_ids"][0]
            else:
                state["teacher_index"] = 0
            self.write_world(2)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()

    def test_choice_source_state_and_continuation_identity_are_not_swappable(self):
        original = deepcopy(self.public_worlds[2])
        for field in ("choice_id", "source_index", "state_index", "continuation_policy_sha256"):
            self.public_worlds[2] = deepcopy(original)
            state = self.public_worlds[2]["states"][0]
            state[field] = state[field]+1 if type(state[field]) is int else "changed"
            self.write_world(2)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()

    def test_complete_flags_and_zero_weight_contract_are_required(self):
        original = deepcopy(self.public_worlds[2])
        for field in ("complete", "no_world_truth", "complete_bundle", "empty_state_and_world_weight", "schema"):
            self.public_worlds[2] = deepcopy(original)
            if field == "complete_bundle":
                self.public_worlds[2]["states"][0][field] = False
            else:
                self.public_worlds[2][field] = False if field in ("complete", "no_world_truth") else "different"
            self.write_world(2)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()

    def test_exported_state_count_cannot_drop_or_duplicate_a_state(self):
        for mutation in ("drop", "duplicate", "count"):
            original = deepcopy(self.public_worlds[2])
            if mutation == "drop":
                self.public_worlds[2]["states"].pop()
            elif mutation == "duplicate":
                self.public_worlds[2]["states"].append(deepcopy(self.public_worlds[2]["states"][0]))
            else:
                self.public_worlds[2]["state_count"] = 1
            self.write_world(2)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "state denominator"):
                self.invoke()
            self.public_worlds[2] = original

    def test_private_extra_world_or_state_fields_are_rejected(self):
        for scope in ("world", "state"):
            original = deepcopy(self.public_worlds[2])
            target = self.public_worlds[2] if scope == "world" else self.public_worlds[2]["states"][0]
            target["true_source_count"] = 10
            self.write_world(2)
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "Unexpected"):
                self.invoke()
            self.public_worlds[2] = original

    def test_manifest_contract_matches_fitter_schema_scale_roles_and_shared_initializations(self):
        original = deepcopy(self.manifest)
        for field, value in (("schema", "other"), ("label_scale", .02), ("counts", {"fit": 36}),
                             ("shared_for_three_independent_initializations", False), ("unrecognized", 1)):
            self.manifest = deepcopy(original)
            self.manifest[field] = value
            self.write_manifest()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoke()

    def test_summary_counts_are_recomputed_including_zero_and_teacher_only_cases(self):
        original = deepcopy(self.manifest)
        for key in ("state_bundles", "nonreference_labels", "teacher_only_states", "zero_state_worlds"):
            self.manifest = deepcopy(original)
            self.manifest[key] += 1
            self.write_manifest()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Public count differs"):
                self.invoke()

    def test_unlisted_public_world_file_is_rejected(self):
        write_json(self.dataset/"unlisted.json.gz", self.public_worlds[0])
        with self.assertRaisesRegex(ValueError, "Extra/missing public dataset files"):
            self.invoke()

    def test_public_world_content_hash_must_match_manifest(self):
        path = self.dataset/self.manifest["worlds"][0]["path"]
        changed = deepcopy(self.public_worlds[0])
        changed["world_id"] = "changed"
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, "path/hash mismatch"):
            self.invoke()


class ArchiveFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = self.enterContext(tempfile.TemporaryDirectory(prefix="synthetic-archive-audit-"))
        self.repo = Path(self.temporary)/"repo"
        self.preflight = self.repo/"preflight"
        self.preflight.mkdir(parents=True)
        self.contents = {"source": {"pkg/a.py": b"# synthetic a\n", "pkg/b.py": b"# synthetic b\n"},
                         "input": {"data/public.json": b'{"synthetic_public":true}\n'}}
        self.freeze, self.record = {}, {}
        for role in ("source", "input"):
            for name, content in self.contents[role].items():
                path = self.repo/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            self.freeze[role] = dict(files={name: hashlib.sha256(content).hexdigest()
                                           for name, content in self.contents[role].items()})
            self.record[role] = dict(members=len(self.contents[role]), provenance={"synthetic": True},
                                    reconstructed_members=[])
            write_json(self.preflight/f"{role}_freeze.json", self.freeze[role])
            self.rebuild(role)

    def rebuild(self, role, *, members=None, embedded=None):
        if embedded is None:
            embedded = dict(files=self.freeze[role]["files"], provenance=self.record[role]["provenance"],
                            reconstructed_members=self.record[role]["reconstructed_members"])
        if members is None:
            members = list(self.contents[role].items())
        archive = self.preflight/("sources.zip" if role == "source" else "inputs.zip")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive, "w") as handle:
                for name, content in members:
                    handle.writestr(name, content)
                handle.writestr("_SOURCE_ARCHIVE_MANIFEST.json", json.dumps(embedded, sort_keys=True))
        self.record[role]["sha256"] = digest_file(archive)
        write_json(self.preflight/f"{role}_archive.json", self.record[role])

    def invoke(self):
        return archive_audit.audit(self.repo, self.preflight)

    def test_source_and_input_zip_embedded_and_live_bytes_all_match(self):
        result = self.invoke()
        self.assertEqual(result["status"], "source_and_input_archives_exactly_verified")
        self.assertEqual([(row["role"], row["members"]) for row in result["checks"]],
                         [("source", 2), ("input", 1)])
        self.assertEqual(result["actual_environment_calls"], 0)
        self.assertEqual(result["actual_optimizer_updates"], 0)

    def test_archive_record_digest_or_member_count_mismatch_is_rejected(self):
        original = deepcopy(self.record["source"])
        for key, value in (("sha256", "0"*64), ("members", 99)):
            modified = deepcopy(original)
            modified[key] = value
            write_json(self.preflight/"source_archive.json", modified)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "digest/count"):
                self.invoke()

    def test_missing_extra_and_duplicate_zip_members_are_rejected_even_after_rehash(self):
        original = list(self.contents["source"].items())
        for mutation in ("missing", "extra", "duplicate"):
            members = original[:-1] if mutation == "missing" else original+[("extra.py", b"extra")] if mutation == "extra" else original+[original[0]]
            self.rebuild("source", members=members)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "member set"):
                self.invoke()

    def test_embedded_manifest_cannot_change_files_provenance_or_reconstruction_record(self):
        for key, value in (("files", {}), ("provenance", {"synthetic": False}),
                           ("reconstructed_members", ["pkg/a.py"])):
            embedded = dict(files=deepcopy(self.freeze["source"]["files"]),
                provenance=deepcopy(self.record["source"]["provenance"]), reconstructed_members=[])
            embedded[key] = value
            self.rebuild("source", embedded=embedded)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Embedded archive manifest"):
                self.invoke()

    def test_live_file_change_cannot_be_hidden_by_matching_zip_and_freeze(self):
        (self.repo/"pkg/a.py").write_bytes(b"# changed live synthetic bytes\n")
        with self.assertRaisesRegex(ValueError, "Archived/live content mismatch"):
            self.invoke()

    def test_changed_archived_member_cannot_pass_with_only_outer_archive_rehashed(self):
        members = list(self.contents["source"].items())
        members[0] = (members[0][0], b"# changed archive synthetic bytes\n")
        self.rebuild("source", members=members)
        with self.assertRaisesRegex(ValueError, "Archived/live content mismatch"):
            self.invoke()

    def test_archive_crc_is_checked_even_when_archive_sha_record_is_updated(self):
        path = self.preflight/"sources.zip"
        with zipfile.ZipFile(path) as handle:
            info = handle.getinfo("pkg/a.py")
            offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        content = bytearray(path.read_bytes())
        content[offset] ^= 1
        path.write_bytes(content)
        self.record["source"]["sha256"] = digest_file(path)
        write_json(self.preflight/"source_archive.json", self.record["source"])
        with self.assertRaisesRegex(ValueError, "CRC failure"):
            self.invoke()


if __name__ == "__main__":
    unittest.main()
