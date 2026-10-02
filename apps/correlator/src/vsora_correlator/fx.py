"""Reference rectangular-window FX with explicit phase/delay corrections."""
import numpy as np


def correction_phase(frequencies_hz, delay_s):
    return np.exp(-2j*np.pi*np.asarray(frequencies_hz)[:,None]*np.asarray(delay_s)[None,:])


def fx_correlate(samples, sample_rate_hz, fft_length=64, center_frequency_hz=1.42e9,
                 delay_s=None, valid=None):
    """samples[station,sample], voltage in sqrt(Jy), output [channel,baseline]."""
    x=np.asarray(samples)
    if x.ndim!=2 or not np.iscomplexobj(x) or not np.isfinite(x).all():
        raise ValueError('finite complex station/sample array required')
    if sample_rate_hz<=0 or fft_length<2 or len(x)<2 or x.shape[1]%fft_length:
        raise ValueError('invalid FX dimensions/sample rate')
    pairs=np.array([(i,j) for i in range(len(x)) for j in range(i+1,len(x))])
    blocks=x.reshape(len(x),-1,fft_length).transpose(1,2,0)
    block_valid=np.ones((len(blocks),len(x)),bool)
    if valid is not None:
        v=np.asarray(valid,dtype=bool)
        if v.shape!=x.shape: raise ValueError('valid mask shape mismatch')
        block_valid=v.reshape(len(x),-1,fft_length).all(axis=2).T
    frequency=center_frequency_hz+np.fft.fftfreq(fft_length,d=1/sample_rate_hz)
    spectrum=np.fft.fft(blocks,axis=1,norm='ortho')
    if delay_s is not None:
        if np.asarray(delay_s).shape!=(len(x),): raise ValueError('station delay shape mismatch')
        spectrum*=correction_phase(frequency,delay_s)[None,:,:]
    out=np.zeros((fft_length,len(pairs)),complex)
    counts=np.zeros(len(pairs),int)
    for b,(i,j) in enumerate(pairs):
        good=block_valid[:,i]&block_valid[:,j]
        counts[b]=good.sum()
        if counts[b]>0:
            out[:,b]=np.mean(spectrum[good,:,i]*spectrum[good,:,j].conj(),axis=0)
    return {'vis_jy':out,'pairs':pairs,'frequencies_hz':frequency,'valid_fft_count':counts,
            'integration_s':counts*fft_length/sample_rate_hz,
            'normalization':'unitary FFT, mean of nonoverlapping rectangular blocks'}
