import numpy as np
import pytest
from scipy.special import j0
from workflows.periodic_phase_validation import predicted_coherence
from workflows.vdif_closure_validation import make_fixture


def test_full_period_and_common_phase_coherence():
    assert predicted_coherence(0.,32.)==pytest.approx(1.+0j)
    assert predicted_coherence(.8,32.)==pytest.approx(j0(.8)+0j,abs=1e-10)
    assert abs(predicted_coherence(.8,.5))<1.


@pytest.mark.parametrize('frequency,amplitudes',[
    (0.,[0,.1,0,0]),(-1.,[0,0,0,0]),(True,[0,0,0,0]),
    (np.nan,[0,0,0,0]),(32.,[0,np.inf,0,0]),(32.,[0,11,0,0]),(32.,[0,0])])
def test_invalid_phase_fixture_before_writing(tmp_path,frequency,amplitudes):
    with pytest.raises(ValueError,match='phase amplitudes'):
        make_fixture(tmp_path/'input',frame_count=4,phase_modulation_hz=frequency,phase_modulation_amplitudes_rad=amplitudes)
    assert not (tmp_path/'input').exists()
