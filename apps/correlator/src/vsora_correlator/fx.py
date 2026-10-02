"""Reference rectangular-window FX with explicit phase/delay corrections."""
import numpy as np
from .quality import channel_diagnostics


def correction_phase(frequencies_hz, delay_s):
    return np.exp(-2j*np.pi*np.asarray(frequencies_hz)[:,None]*np.asarray(delay_s)[None,:])


def remove_fringe_rate(samples,sample_rate_hz,rate_hz,time_offset_s=0.,time_reference_s=0.):
    """Derotate estimated station rates before accumulating FFT products."""
    x=np.asarray(samples);rate=np.asarray(rate_hz,float)
    if x.ndim!=2 or rate.shape!=(len(x),) or not np.isfinite(rate).all() or sample_rate_hz<=0:
        raise ValueError('invalid rate correction dimensions')
    t=time_offset_s+np.arange(x.shape[1])/sample_rate_hz-time_reference_s
    return x*np.exp(-2j*np.pi*rate[:,None]*t[None,:])


def fx_correlate(samples, sample_rate_hz, fft_length=64, center_frequency_hz=1.42e9,
                 delay_s=None, valid=None,spectral_quality=None):
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
    result={'vis_jy':out,'pairs':pairs,'frequencies_hz':frequency,'valid_fft_count':counts,
            'integration_s':counts*fft_length/sample_rate_hz,
            'normalization':'unitary FFT, mean of nonoverlapping rectangular blocks'}
    if spectral_quality is not None:
        result.update(channel_diagnostics(spectrum,block_valid,frequency,spectral_quality))
    return result


def fx_correlate_series(samples,sample_rate_hz,fft_length=128,blocks_per_integration=128,
                        center_frequency_hz=1.42e9,delay_s=None,valid=None,time_offset_s=0.,spectral_quality=None):
    """Short integrations keep residual rate information; sorted RF channels.

    Noise weights use measured total station powers (including the sky) with
    the independent-receiver approximation. They are not a receiver flux cal.
    """
    x=np.asarray(samples)
    if x.ndim!=2 or not isinstance(blocks_per_integration,int) or blocks_per_integration<1:
        raise ValueError('invalid integration dimensions')
    if not isinstance(fft_length,int) or fft_length<2: raise ValueError('invalid FFT length')
    ns=fft_length*blocks_per_integration
    if x.shape[1]==0 or x.shape[1]%ns: raise ValueError('whole short integrations required')
    validity=np.ones(x.shape,bool) if valid is None else np.asarray(valid,dtype=bool)
    if validity.shape!=x.shape: raise ValueError('valid mask shape mismatch')
    output=[];weights=[];counts=[];durations=[];diagnostics={}
    for index in range(x.shape[1]//ns):
        sl=slice(index*ns,(index+1)*ns);data=x[:,sl];ok=validity[:,sl]
        result=fx_correlate(data,sample_rate_hz,fft_length,center_frequency_hz,delay_s,ok,spectral_quality)
        power=np.array([np.mean(abs(data[i,ok[i]])**2) if ok[i].any() else 0 for i in range(len(x))])
        pairpower=power[result['pairs'][:,0]]*power[result['pairs'][:,1]]
        if spectral_quality is not None and spectral_quality['channel_weights']:
            p=result['diagnostic_station_power'];i,j=result['pairs'].T
            pairpower=p[:,i]*p[:,j]
        weight=np.divide(2*result['valid_fft_count'],pairpower,out=np.zeros_like(pairpower),where=pairpower>0)
        weight=np.broadcast_to(weight,result['vis_jy'].shape).copy()
        if spectral_quality is not None:
            flags=result['diagnostic_station_flags'];i,j=result['pairs'].T
            weight[(flags[:,i]!=0)|(flags[:,j]!=0)]=0
        order=np.argsort(result['frequencies_hz'])
        output.append(result['vis_jy'][order]);weights.append(weight[order])
        for k,value in result.items():
            if k.startswith('diagnostic_'):
                diagnostics.setdefault(k,[]).append(value if k.endswith('valid_fft_count') else value[order])
        counts.append(result['valid_fft_count']);durations.append(result['integration_s'])
    return {**{k:np.array(v) for k,v in diagnostics.items()},'vis_jy':np.array(output),'weights':np.array(weights),'pairs':result['pairs'],
            'frequencies_hz':result['frequencies_hz'][order],
            'times_s':time_offset_s+(np.arange(len(output))+.5)*ns/sample_rate_hz,
            'integration_s':np.array(durations),'valid_fft_count':np.array(counts),
            'noise_weight_assumption':('2*valid FFT blocks / product of measured station channel powers; weak-source quadrature approximation'
                 if spectral_quality is not None and spectral_quality['channel_weights']
                 else '2*valid FFT blocks / product of measured station total powers')}
