"""各固定罰則の実RML結果を、同じ設定の公開画像目的関数へ照合する。"""
from itertools import combinations
import numpy as np
import pytest
from vsora_imaging.rml import fit_closure_image
from vsora_simulator.visibility import direct_visibility
from workflows.regularizer_image_validation import PRESETS,initial_reference,score_regularizer_setting
from workflows.temporal_image_validation import SETTINGS,partition_input
from workflows.image_grid_validation import embed_on_32


@pytest.mark.parametrize('name',['baseline',*PRESETS])
def test_actual_small_rml_matches_own_objective_and_shared_initial_formula(name):
    rng=np.random.default_rng(128);stations=rng.normal(0,300,(4,3));pairs=np.array(list(combinations(range(4),2)));uvw=(stations[pairs[:,0]]-stations[pairs[:,1]])[None,None];uvw=np.concatenate([uvw,uvw*1.01],axis=0)
    truth=np.zeros((8,8));truth[4,4]=.7;truth[3,5]=.3;v=direct_visibility(uvw,truth,64.)+(.003+.002j)
    d={'visibilities':v,'weights':np.full(v.shape,1e4),'pairs':pairs,'uvw_lambda':uvw,'times_s':np.array([0.,1.]),'frequencies_hz':np.array([1.42e9]),'integration_s':np.ones((2,6)),
       'metadata':{'visibility_unit':'ADC^2','config':{'source':{'ra_deg':1.,'dec_deg':2.},'observation':{'frequency_hz':1.42e9},'image':{'pixels':8,'pixel_arcsec':64.}}}}
    settings={**SETTINGS,**({} if name=='baseline' else PRESETS[name]),'starts':1,'max_iterations':2};mask=np.array([True,False]);training=partition_input(d,mask)
    own=initial_reference(training,settings);base=initial_reference(training,{**settings,'entropy':.01,'tsv':.0001,'centroid':.1})
    for k in own:np.testing.assert_array_equal(own[k],base[k])
    image,summary=fit_closure_image(training['uvw_lambda'],training['visibilities'],training['weights'],training['pairs'],**settings);science,embedded=score_regularizer_setting(d,mask,image,summary,truth,embed_on_32(truth),settings)
    assert science['own_settings']==settings and not science['truth_or_unused_values_used_for_selection']
    metrics=science['evaluation']['training']['fit']['public_api']['metrics']
    for key in ['entropy','tsv','centroid']:
        if settings[key]==0:assert metrics[key+'_loss']==0.
    if name=='data_only':assert metrics['objective']==metrics['data_loss']
