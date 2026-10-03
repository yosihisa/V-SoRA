"""Exact known Gaussian second moments for station-specific finite operators."""
import numpy as np
from scipy.signal import firwin
from .visibility_moments import visibility_noise_moments


def aligned_fft_kernel(fft_length,channel_index,fractional_sample_offset=0.):
    """Reference equal-rate FIR + fixed sinc offset + one shifted FFT channel.

    Coefficients h[r] multiply raw samples x[a*fft_length+r]. The raw origin
    is 64 samples before the aligned integer origin. No varying clock/rate,
    quantization, missing samples, actual receiver spectrum or geometry here.
    """
    if (isinstance(fft_length,bool) or not isinstance(fft_length,(int,np.integer))
            or not 8<=fft_length<=1024 or fft_length&(fft_length-1)
            or isinstance(channel_index,bool) or not isinstance(channel_index,(int,np.integer))
            or not 0<=channel_index<fft_length or isinstance(fractional_sample_offset,(bool,np.bool_))
            or not np.isscalar(fractional_sample_offset) or np.iscomplexobj(fractional_sample_offset)
            or not np.isfinite(fractional_sample_offset)
            or not 0<=fractional_sample_offset<1):
        raise ValueError('power-of-two FFT 8..1024, valid integer channel, fixed offset in [0,1) required')
    taps=firwin(65,.35,fs=1.,window=('kaiser',8.6))
    distance=fractional_sample_offset-np.arange(-32,33)
    coeff=np.sinc(distance)*np.where(abs(distance)<=32,.5*(1+np.cos(np.pi*distance/32)),0.)
    coeff/=coeff.sum()
    aligned=np.convolve(coeff,taps[::-1])
    index=(channel_index+fft_length//2)%fft_length
    fourier=np.exp(-2j*np.pi*index*np.arange(fft_length)/fft_length)/np.sqrt(fft_length)
    return np.convolve(fourier,aligned)


def filtered_visibility_moments(station_covariance,kernels,stride,samples,pairs=None):
    """x[n] iid proper Gaussian; y_i[a]=sum h_i[r] x_i[a*stride+r].

    V_ij=mean_a y_i[a] conj(y_j[a]). Uses all finite output time lags;
    exact Gaussian moments, no Gaussian visibility distribution assumption.
    """
    s=np.asarray(station_covariance,complex);h=np.asarray(kernels,complex)
    if (s.ndim!=2 or not 2<=len(s)<=8 or h.ndim!=2 or h.shape[0]!=len(s)
            or not 1<=h.shape[1]<=4096 or not np.isfinite(h).all()
            or isinstance(stride,bool) or not isinstance(stride,(int,np.integer)) or stride<1
            or isinstance(samples,bool) or not isinstance(samples,(int,np.integer)) or not 1<=samples<=2**53):
        raise ValueError('2..8 stations, finite kernels, positive integer stride/count required')
    base=visibility_noise_moments(s,1,pairs);p=base['pairs'];s=(s+s.conj().T)/2
    lag_count=min(samples-1,(h.shape[1]-1)//stride)
    if len(s)**2*h.shape[1]*(lag_count+1)>10_000_000:
        raise ValueError('filtered noise reference operator exceeds work limit')
    with np.errstate(over='ignore',invalid='ignore'):
        energy=np.sum(abs(h)**2,axis=1)
    if not np.isfinite(energy).all() or np.any(energy<=0):raise ValueError('positive finite kernel energy required')
    station_lags=[]
    with np.errstate(over='ignore',invalid='ignore'):
        for d in range(lag_count+1):
            shift=d*stride
            left=h if not shift else h[:,:-shift];right=h if not shift else h[:,shift:]
            station_lags.append(s*(left @ right.conj().T))
    lags=np.asarray(station_lags)
    if not np.isfinite(lags).all():raise ValueError('station lag covariance exceeds finite numerical range')
    i,j=p.T;b=len(p);gamma=np.zeros((b,b),complex);pseudo=gamma.copy()
    with np.errstate(over='ignore',invalid='ignore'):
        for d,r in enumerate(lags):
            weight=(1-d/samples)/samples
            for value in ([r] if d==0 else [r,r.conj().T]):
                opposite=value.conj().T
                gamma+=weight*value[i[:,None],i[None,:]]*opposite[j[None,:],j[:,None]]
                pseudo+=weight*value[i[:,None],j[None,:]]*opposite[i[None,:],j[:,None]]
        real=.5*np.block([[np.real(gamma+pseudo),np.imag(pseudo-gamma)],
                         [np.imag(pseudo+gamma),np.real(gamma-pseudo)]])
    if not np.isfinite(real).all() or not np.isfinite(gamma).all() or not np.isfinite(pseudo).all():
        raise ValueError('filtered visibility moments exceed finite numerical range')
    iid=visibility_noise_moments(lags[0],samples,p)
    identical=bool(np.array_equal(h,np.broadcast_to(h[0],h.shape)))
    factor=None
    if identical:
        scalar=[np.sum(h[0,:-d*stride]*h[0,d*stride:].conj()) for d in range(1,lag_count+1)]
        factor=float(1+2*sum((1-d/samples)*abs(r/energy[0])**2 for d,r in enumerate(scalar,1)))
    return {'pairs':p.copy(),'mean':lags[0][i,j].copy(),'station_output_covariance':lags[0],
        'positive_time_lag_station_covariance':lags,'maximum_included_lag_blocks':int(lag_count),
        'complex_covariance':gamma,'complex_pseudocovariance':pseudo,'real_covariance':(real+real.T)/2,
        'real_parameter_order':'all real baselines, then all imaginary baselines',
        'iid_counterfactual_real_covariance':iid['real_covariance'],'nominal_output_samples':int(samples),
        'output_stride_raw_samples':int(stride),'identical_station_kernels':identical,
        'common_kernel_variance_factor':factor,'common_kernel_effective_count':None if factor is None else float(samples/factor),
        'distribution_gaussian_assumed':False,'raw_covariance_supplied':True,
        'actual_hardware_data':False,'production_rml_noise_model_changed':False,
        'limits':'Known constant iid proper Gaussian raw station covariance and fixed finite station operators. No measured effective count, colored raw input, variable resampling, ADC, flags, gain/rate drift, hardware confidence or image fidelity.'}
