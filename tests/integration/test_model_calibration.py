import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times,ARCSEC_RAD
from vsora_formats.spectral import save_spectral
from vsora_correlator.session import calibrate_shard


def test_shape_calibration_against_independent_two_point_formula(tmp_path):
    repo=Path(__file__).resolve().parents[2]
    c=load_config(repo/'configs/experiments/ideal-point.json');c['source']['model']='double'
    t=np.arange(16)*.02;f=1.42e9+np.arange(-8,8)*128000
    g=geometry_at_times(c,Time(c['observation']['start_utc'])+t*u.s)
    uvw=g['uvw_lambda'][:,None,:,:]*(f[None,:,None,None]/1.42e9)
    l=80*ARCSEC_RAD;n=np.sqrt(1-l*l)
    # Formula written here independently of synthetic_sky/direct_visibility.
    model=600*np.exp(-2j*np.pi*(-uvw[...,0]*l+uvw[...,2]*(n-1)))
    model+=400*np.exp(-2j*np.pi*(uvw[...,0]*l+uvw[...,2]*(n-1)))
    amplitude=np.array([4.8,3.2,4.4,3.6]);delay=np.array([0,2.3e-6,-1.7e-6,.38e-6]);rate=np.array([0,2.7,-1.3,4.1])
    gain=amplitude*np.exp(1j*(np.array([0,.4,-.7,1.4])+2*np.pi*(
         (t[:,None,None]-t.mean())*rate+(f[None,:,None]-f.mean())*delay)))
    p=g['pairs'];v=model*gain[...,p[:,0]]*gain[...,p[:,1]].conj()
    cube={'visibilities':v,'weights':np.ones(v.shape),'pairs':p,'times_s':t,'frequencies_hz':f,
          'uvw_lambda':uvw,'integration_s':np.ones((len(t),len(p)))*.02}
    meta={'visibility_unit':'ADC^2','config':c,'time_origin_utc':c['observation']['start_utc'],
          'phase_center_corrected':True,'rate_applied_hz':[0.]*4,'rate_applied_reference_s':0.}
    save_spectral(tmp_path/'raw.npz',cube,meta);(tmp_path/'model.json').write_text(json.dumps(c))
    cal=calibrate_shard(tmp_path/'raw.npz',tmp_path/'shape.json',model_config=tmp_path/'model.json')
    np.testing.assert_allclose(cal['amplitude'],amplitude,rtol=1e-8)
    np.testing.assert_allclose(cal['delay_s'],delay,rtol=0,atol=1e-13)
    np.testing.assert_allclose(cal['rate_hz'],rate,rtol=0,atol=1e-7)
    assert cal['model_kind']=='double' and cal['assumed_model_flux_jy']==1000
