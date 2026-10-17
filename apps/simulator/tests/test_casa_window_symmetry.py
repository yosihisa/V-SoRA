"""Software checks; small profiles are not statistical observing evidence."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from vsora_observation.reference import reference_path
from vsora_simulator.casa_window_symmetry import case_plan, experiment, run, _known_model


def small(mode='point'):
    c=case_plan('smoke')[0]
    c.update(mode=mode,case_id='small-'+mode,trials=8)
    return c


def test_fixed_full_plan_before_outcomes():
    p=case_plan()
    assert len(p)==53 and len({c['case_id'] for c in p})==53
    assert all(c['windows']==8 and c['formal_mc_precision'] for c in p)
    assert all(c['trials']==1024 for c in p[:36]+p[46:])
    assert all(c['trials']==256 and c['modes']==19200 for c in p[36:46])
    assert {c['modes'] for c in p[:36]}=={128,512}
    assert {c['maximum_baseline_m'] for c in p}=={25.,100.,600.}
    assert p[30]['seed']==p[50]['seed']==p[51]['seed']
    assert p[47]['receiver_sefd_jy']==[1000.,2000.,4000.,8000.]*2
    assert all(c['trials']==16 and not c['formal_mc_precision'] for c in case_plan('smoke'))


def test_reference_asset_and_frozen_visibility_provenance():
    q=json.loads(reference_path('known-casa-window-symmetry.json').read_text())
    original=Path(__file__).resolve().parents[3]/'validation/runs/stage081/known-array-scale.json'
    assert q['source_result_sha256']==hashlib.sha256(original.read_bytes()).hexdigest()
    assert q['reference']['derived_sha256']==hashlib.sha256(reference_path().read_bytes()).hexdigest()
    for maximum in (25.,100.,600.):
        s,root,residual,flux=_known_model('casa',maximum,(1000.,)*8)
        np.testing.assert_allclose(root @ root.conj().T,s,rtol=1e-12,atol=1e-9)
        assert flux==pytest.approx(1000.) and residual>=0
        assert not s.flags.writeable and not root.flags.writeable
    with pytest.raises(ValueError):reference_path('../known-casa-window-symmetry.json')


@pytest.mark.parametrize('mode',['point','zero','heterogeneous_point','equal_double','known_inverse'])
def test_known_conjugation_symmetric_models(mode):
    c=small(mode)
    if mode=='heterogeneous_point':c['receiver_sefd_jy']=[1000.,2000.,4000.,8000.]*2
    original=copy.deepcopy(c);q=experiment(c)
    assert c==original and q['state']=='complete'
    assert q['joint_null_invariance_supported_by_generation']
    assert q['spatial_covariance_real_gauge_relative_residual']<1e-10
    assert q['gain_p_values_identical'] and q['maximum_gain_feature_abs_difference']<2e-12
    assert q['maximum_conjugation_transport_abs_difference']<2e-12
    assert not any(r['null_mc_check_applied'] for r in q['levels'])
    assert all(r['within_nominal_plus_6_reference_se'] is None for r in q['levels'])


@pytest.mark.parametrize('mode',['casa','unequal_double','quadratic_phase','copied_windows'])
def test_alternatives_not_forced_to_reject(mode):
    q=experiment(small(mode))
    assert q['state']=='complete' and not q['joint_null_invariance_supported_by_generation']
    assert not q['unknown_lo_estimated'] and not q['rml_image_generated']
    if mode=='copied_windows':
        assert not q['window_draws_independent']
        assert q['p_value_histogram']==[{'tail_count':2,'count':8}]
        assert all(r['fraction']==1 for r in q['levels'])


def test_true_inverse_matches_same_finite_realization():
    point=experiment(small());inverse=experiment(small('known_inverse'))
    assert inverse['maximum_known_inverse_feature_abs_difference']<2e-12
    assert point['p_value_histogram']==inverse['p_value_histogram']
    np.testing.assert_allclose(point['mc_mean_window_imaginary_features'],inverse['mc_mean_window_imaginary_features'],atol=1e-14)
    assert inverse['known_truth_inverse_phase_applied'] and not inverse['unknown_lo_estimated']


def test_smoke_roundtrip_and_no_overwrite(tmp_path):
    out=tmp_path/'small';progress=[]
    q=run(out,'smoke',lambda *args:progress.append(args))
    assert q==json.loads((out/'summary.json').read_text())
    assert len(q['cases'])==len(progress)==3 and q['software_smoke_only']
    assert len(list((out/'cases').glob('*.json')))==3
    assert (out/'casa-window-symmetry.png').is_file()
    for c in q['cases']:assert c==json.loads((out/'cases'/(c['case_id']+'.json')).read_text())
    assert not q['adc_fft_fir_quantization_vdif_processed'] and not q['image_reconstructed']
    with pytest.raises(FileExistsError):run(out,'smoke')


@pytest.mark.parametrize('key,value',[
    ('modes',True),('modes',2),('modes',19201),('modes',16.),
    ('windows',0),('windows',13),('windows',True),('trials',1),('trials',4097),
    ('seed',-1),('seed',2**32),('seed',False),('mode','unknown'),
    ('maximum_baseline_m',50.),('case_id','../escape'),('case_id',None),
    ('receiver_sefd_jy',[1000.]*7),('receiver_sefd_jy',[np.nan]*8),
    ('receiver_sefd_jy',[99.]*8),('receiver_sefd_jy',[1e8]*8),
    ('receiver_sefd_jy',[1000.+1j]*8),('receiver_sefd_jy',[True]*8),
    ('receiver_sefd_jy',np.ma.array([1000.]*8,mask=True)),
    ('formal_mc_precision',1),('formal_mc_precision',True)])
def test_invalid_cases(key,value):
    c=small();c[key]=value
    with pytest.raises(ValueError):experiment(c)


@pytest.mark.parametrize('profile',['unknown',None,True])
def test_invalid_profiles(profile):
    with pytest.raises(ValueError):case_plan(profile)


def test_case_dictionary_required():
    with pytest.raises(ValueError):experiment(None)
