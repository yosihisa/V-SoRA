"""未知の天空・局gainのまま、pilotの検出基線graphを記録する。"""
import argparse
import json
from numbers import Real
from pathlib import Path
import numpy as np
from .rate import validate_pilot_arrays, _baseline_rate_records


def diagnose_rate_graph(data, *, reference_station=0, max_rate_hz=100., min_snr=8., min_peak_z=8.):
    """連結は必要条件だけ。局解のchisqや物理的位相の成功を認定しない。"""
    v, w, t, pairs, dt = validate_pilot_arrays(data)
    stations = sorted(set(pairs.ravel().tolist()))
    if type(reference_station) is not int or reference_station not in stations:
        raise ValueError('reference station must be a present integer station')
    for value in (max_rate_hz, min_snr, min_peak_z):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError('positive finite search and detection settings required')
        if not np.isfinite(value) or value <= 0:
            raise ValueError('positive finite search and detection settings required')
    if max_rate_hz >= .5/dt[0]: raise ValueError('rate search must be below the temporal Nyquist limit')
    epoch, records = _baseline_rate_records(v, w, t, pairs, dt, max_rate_hz, min_snr, min_peak_z)
    neighbours = {s: set() for s in stations}; reasons = {}
    for record in records:
        if record['accepted']:
            i, j = record['pair']; neighbours[i].add(j); neighbours[j].add(i)
        else:
            reason = record['reason']; reasons[reason] = reasons.get(reason, 0) + 1
    unseen = set(stations); components = []
    while unseen:
        pending = [min(unseen)]; component = set()
        while pending:
            station = pending.pop()
            if station in component: continue
            component.add(station); pending.extend(neighbours[station] - component)
        unseen -= component; components.append(sorted(component))
    connected = len(components) == 1
    reference_component = next(group for group in components if reference_station in group)
    return {'schema_version': 1, 'type': 'pilot_rate_graph_diagnostic',
            'state': 'connected' if connected else 'disconnected',
            'station_indices': stations, 'reference_station': reference_station,
            'components': components, 'reference_component': reference_component,
            'stations_outside_reference_component': sorted(set(stations) - set(reference_component)),
            'isolated_stations': [s for s in stations if not neighbours[s]],
            'graph_rank': len(stations) - len(components), 'required_graph_rank': len(stations) - 1,
            'accepted_baselines': sum(record['accepted'] for record in records),
            'rejected_baselines': reasons, 'baseline_estimates': records,
            'pilot_integrations': len(t), 'pilot_span_s': float(t[-1] - t[0] + dt[0]),
            'sample_cadence_s': float(dt[0]), 'time_reference_s': epoch,
            'max_baseline_rate_hz': float(max_rate_hz), 'temporal_nyquist_hz': float(.5/dt[0]),
            'min_coherent_snr': float(min_snr), 'min_noise_peak_z': float(min_peak_z),
            'station_solution_attempted': False, 'false_alarm_probability_calibrated': False,
            'initial_baseline_rate_bound_externally_required': True,
            'limits': 'Same finite baseline search as rate estimator; graph connection is necessary, not a solution consistency, alias, physical coherence or imaging guarantee. Search thresholds are not a calibrated false-alarm probability. Short stable sky/gain and nominal independent circular noise assumptions remain.'}


def main():
    from vsora_formats.spectral import load_spectral
    p = argparse.ArgumentParser(description='pilotの採用/棄却基線と局graphを保存')
    p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    p.add_argument('--reference-station', type=int, default=0); p.add_argument('--max-rate-hz', type=float, default=100.)
    p.add_argument('--min-snr', type=float, default=8.); p.add_argument('--min-peak-z', type=float, default=8.)
    args = vars(p.parse_args()); source = args.pop('input'); output = Path(args.pop('output'))
    result = diagnose_rate_graph(load_spectral(source), **args)
    with output.open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__': main()
