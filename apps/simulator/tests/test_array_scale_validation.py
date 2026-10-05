import numpy as np
import pytest
from workflows.array_scale_validation import run


@pytest.fixture(scope='module')
def comparison(tmp_path_factory):
    return run(tmp_path_factory.mktemp('array-parent')/'new')


@pytest.mark.parametrize('layout',['spread','line','ring'])
@pytest.mark.parametrize('maximum',[25.,50.,100.,200.,400.,600.])
def test_geometry_population_and_scale_records(comparison,layout,maximum):
    rows=[r for r in comparison['snapshots'] if r['layout']==layout]
    row=next(r for r in rows if r['maximum_baseline_m']==maximum)
    largest=next(r for r in rows if r['maximum_baseline_m']==600.)
    assert row['actual_maximum_pair_distance_m']==pytest.approx(maximum,rel=1e-14)
    # GCRS positions are Earth-sized before subtracting the station positions.
    # Bound the cancellation by64 ulps of a6.4Mm position, in wavelengths.
    rounding_lambda=64*np.spacing(6.4e6)*comparison['assumed_frequency_hz']/299792458.
    assert abs(row['maximum_projected_baseline_lambda']-largest['maximum_projected_baseline_lambda']*maximum/600.)<=rounding_lambda
    assert row['smallest_projected_fringe_period_arcsec']*row['maximum_projected_baseline_lambda']==pytest.approx(206264.80624709636,rel=1e-14)
    assert row['point_population_signature_max_abs']<1e-12
    assert row['population_signature']['phase_valid_rows']==56
    assert row['population_signature']['logamp_valid_rows']==140
    assert row['population_signature']['image_information_or_confidence_calculated'] is False
    cases=[c for c in comparison['conditional_scale_cases'] if c['snapshot_id']==row['id']]
    assert len(cases)==6
    for case in cases:
        assert case['independent_samples_conditional_input']==round(64000*case['window_seconds'])
        assert len(case['known_mean_real_imag'])==56
        assert case['complex_rms_scale_median']==np.median(case['known_complex_rms_scale'])


def test_run_scope_and_dimensions(comparison):
    assert len(comparison['snapshots'])==18
    assert len(comparison['conditional_scale_cases'])==108
    assert comparison['maximum_sky_gram_vs_direct_visibility_difference_jy']<1e-9
    assert comparison['assumed_frequency_hz']==1.42e9
    assert comparison['image_pixels']==64
    assert comparison['population_closure_rms_is_image_information_rank'] is False
    assert comparison['actual_hardware_data'] is False
    assert comparison['optimal_array_selected'] is False
    assert comparison['image_reconstructed'] is False


def test_existing_output_rejected(tmp_path):
    with pytest.raises(FileExistsError):run(tmp_path)
