"""新しい画像workflowの情報分離・入力保持・run選択を確認する。"""
import numpy as np
import pytest
from workflows.short_integration_images import FIELDS,fitter_data,identities,validate_selection


def input_data():
    data={k:np.arange(6,dtype=float) for k in FIELDS}
    data['metadata']={'visibility_unit':'ADC^2','rate_applied_hz':[0.,17.], 'config':{
        'source':{'model':'unknown','ra_deg':350.,'dec_deg':58.},
        'observation':{'frequency_hz':1.42e9,'start_utc':'2026-10-02T10:00:00Z'},
        'image':{'pixels':32,'pixel_arcsec':16.},'stations':[{'sefd_jy':1000.}]}}
    return data


def test_numerical_inputs_preserved_but_clock_rate_sefd_metadata_removed():
    original=input_data();copied=fitter_data(original)
    assert identities(original)==identities(copied)
    assert set(copied['metadata'])=={'config','visibility_unit','generating_truth_supplied_to_fitter'}
    assert set(copied['metadata']['config'])=={'source','observation','image'}
    assert copied['metadata']['config']['observation']=={'frequency_hz':1.42e9}
    copied['visibilities'][0]=99.;assert original['visibilities'][0]==0.


@pytest.mark.parametrize('change',['model','flux'])
def test_generating_sky_metadata_cannot_be_present(change):
    data=input_data();source=data['metadata']['config']['source']
    if change=='model':source['model']='casa'
    else:source['total_flux_jy']=1000.
    with pytest.raises(ValueError,match='unknown observer'):fitter_data(data)


def test_training_objective_selects_run_even_when_it_has_not_converged():
    summary={'runs':[{'objective':2.,'optimizer_success':True},{'objective':1.,'optimizer_success':False}], 'selected_start':1}
    assert validate_selection(summary)==1
    summary['selected_start']=0
    with pytest.raises(ValueError,match='training objective'):validate_selection(summary)


@pytest.mark.parametrize('value',[True,1.,0])
def test_invalid_selection_or_nonfinite_objective_cannot_certify_a_fit(value):
    with pytest.raises(ValueError,match='training objective'):
        validate_selection({'runs':[{'objective':np.nan},{'objective':1.}],'selected_start':value})
