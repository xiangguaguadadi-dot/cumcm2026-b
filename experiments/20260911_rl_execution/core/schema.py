"""Observable-only shared candidate schema. No training labels live here."""
from __future__ import annotations
import hashlib
import json
import math

SCHEMA_VERSION = 'rl-core-snapshot-v1'
GENERATOR_VERSION = 'c7-macro-candidates-v1'
GLOBAL_DIM, CHANNEL_DIM, CANDIDATE_DIM = 16, 12, 16
GLOBAL_FEATURE_NAMES = (
 'mode3','mode4','position_x_4000','position_y_4000','channel_20',
 'virtual_time_360000','elapsed_real_1200','cleared_20','known_20',
 'unknown_20','remaining_stations_49','learning_primitives_10000',
 'no_progress_decisions_32','decisions_10000','remaining_real_1200',
 'previous_macro_seconds_10000')
CHANNEL_FEATURE_NAMES = (
 'channel_20','cleared','has_bearing','bearing_count_64','center_x_1800',
 'center_y_1800','radius_3600','area_over_domain','scanned_fraction',
 'last_bearing_x_4000','last_bearing_y_4000','last_bearing_degrees_360')
CANDIDATE_FEATURE_NAMES = (
 'is_source','is_station','is_fallback','channel_20','station_index_49',
 'target_x_4000','target_y_4000','distance_over_box_diagonal',
 'immediate_cost_proxy_10000','source_radius_3600','source_bearings_64',
 'unobserved_channels_20','successor_x_4000','successor_y_4000',
 'has_successor','source_radius_le_20')

def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def stable_id(payload):
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:24]

def freeze_copy(value):
    """Detached serializable value. Engine never exposes its mutable live state."""
    return json.loads(canonical_json(value))

def validate_snapshot(s):
    assert s['schema_version'] == SCHEMA_VERSION
    n=len(s['candidates'])
    assert 1 <= n <= 64
    assert len(s['global_features']) == GLOBAL_DIM
    assert len(s['channel_features']) == 20
    assert all(len(v)==CHANNEL_DIM for v in s['channel_features'])
    assert len(s['candidate_features'])==n
    assert all(len(v)==CANDIDATE_DIM for v in s['candidate_features'])
    assert len(s['candidate_ids'])==len(s['valid_mask'])==n
    assert len(set(s['candidate_ids']))==n
    assert 0 <= s['teacher_index'] < n
    assert any(s['valid_mask'])
    for rows in [s['global_features'], *s['channel_features'], *s['candidate_features']]:
        assert all(type(v) in (int,float) and math.isfinite(v) for v in rows)
    return True

def teacher_selector(snapshot):
    return int(snapshot['teacher_index'])
