from itertools import combinations
from pathlib import Path
import numpy as np
import pytest
from vsora_observation import load_config
from vsora_formats.spectral import save_spectral,load_spectral
from vsora_imaging.synthesis import merge_spectral


def write(path,origin='2026-10-02T08:00:00Z',unit='ADC^2',frequency=1.42e9,times=(.15,.25),aligned=True):
    config=load_config(Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json')
    config['source']['model']='unknown';config['source'].pop('total_flux_jy')
    p=np.array(list(combinations(range(4),2)));v=np.ones((2,1,6),complex)
    w=np.full(v.shape,1e4);w[0,0,0]=0
    data={'visibilities':v,'weights':w,'pairs':p,'uvw_lambda':np.zeros((*v.shape,3)),
          'times_s':np.array(times),'frequencies_hz':np.array([frequency]),'integration_s':np.full((2,6),.1)}
    save_spectral(path,data,{'config':config,'visibility_unit':unit,'time_origin_utc':origin,
         'phase_center_corrected':True,'clock_mapping_applied':aligned,'nominal_integration_s':.1})


def test_sort_utc_and_preserve_flags_without_averaging(tmp_path):
    write(tmp_path/'early.npz');write(tmp_path/'late.npz','2026-10-02T08:00:10Z')
    result=merge_spectral([tmp_path/'late.npz',tmp_path/'early.npz'],tmp_path/'merged.npz')
    data=load_spectral(tmp_path/'merged.npz')
    assert np.allclose(data['times_s'],[.15,.25,10.15,10.25])
    assert data['visibilities'].shape==(4,1,6)
    assert np.all(data['weights'][[0,2],0,0]==0)
    assert np.allclose(result['exposure_per_baseline_s'],.4)
    assert len(data['metadata']['source_inputs'])==2 and data['metadata']['visibility_unit']=='ADC^2'
    assert data['metadata']['config']['observation']['start_utc']=='2026-10-02T08:00:00.000Z'
    with pytest.raises(FileExistsError):merge_spectral([tmp_path/'early.npz',tmp_path/'late.npz'],tmp_path/'merged.npz')


@pytest.mark.parametrize('options',[{'unit':'Jy'},{'frequency':1.4201e9},{'aligned':False},{'times':(.15,.24)}])
def test_mismatch_or_overlap_is_rejected(tmp_path,options):
    write(tmp_path/'a.npz');write(tmp_path/'b.npz',**options)
    with pytest.raises(ValueError):merge_spectral([tmp_path/'a.npz',tmp_path/'b.npz'],tmp_path/'merged.npz')
    assert not (tmp_path/'merged.npz').exists()
