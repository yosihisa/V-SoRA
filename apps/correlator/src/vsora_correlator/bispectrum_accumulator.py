"""Experimental common-sample raw bispectrum sums, independent of RML."""
from itertools import combinations
import numpy as np


class BispectrumAccumulator:
    """Consume spectrum[FFT block, channel, station] without storing voltage.

    Supplied boolean masks have shape [block, station]. Each triangle uses
    the common valid block set for its three edges. This algebra does not
    establish sample independence, mask ignorability or unbiased phase.
    """
    def __init__(self,stations,channels,triangles=None):
        if (isinstance(stations,bool) or not isinstance(stations,(int,np.integer)) or not 3<=stations<=8
                or isinstance(channels,bool) or not isinstance(channels,(int,np.integer)) or not 1<=channels<=4096):
            raise ValueError('integer stations3..8 and channels1..4096 required')
        if np.ma.isMaskedArray(triangles):raise ValueError('masked triangles unsupported')
        t=np.array(list(combinations(range(stations),3)),dtype=int) if triangles is None else np.asarray(triangles)
        if (t.ndim!=2 or t.shape[1]!=3 or not len(t) or not np.issubdtype(t.dtype,np.integer)
                or np.any(t<0) or np.any(t>=stations) or np.any(t[:,0]>=t[:,1]) or np.any(t[:,1]>=t[:,2])
                or len(np.unique(t,axis=0))!=len(t)):
            raise ValueError('unique canonical integer triangles i<j<k required')
        self.stations=int(stations);self.channels=int(channels);self._triangles=t.copy()
        shape=(self.channels,len(t),3)
        self._a=np.zeros(shape,complex);self._h=np.zeros(shape,complex);self._j=np.zeros(shape[:2],complex)
        self._counts=np.zeros(len(t),np.int64);self._nominal=0;self._maximum_chunk=0
        self._finished=False;self._mask_supplied=False

    def consume(self,spectrum,valid=None):
        if self._finished:raise ValueError('accumulator already finished')
        if np.ma.isMaskedArray(spectrum) or np.ma.isMaskedArray(valid):raise ValueError('masked inputs unsupported')
        x=np.asarray(spectrum)
        if (x.ndim!=3 or x.shape[1:]!=(self.channels,self.stations) or not len(x)
                or not np.iscomplexobj(x) or x.size>8000000 or not np.isfinite(x).all()):
            raise ValueError('finite complex [block,channel,station] chunk, at most8million values required')
        ok=np.ones((len(x),self.stations),bool) if valid is None else np.asarray(valid)
        if ok.dtype!=np.bool_ or ok.shape!=(len(x),self.stations):raise ValueError('boolean [block,station] valid mask required')
        a=np.zeros_like(self._a);h=np.zeros_like(self._h);j=np.zeros_like(self._j);count=np.zeros_like(self._counts)
        with np.errstate(over='ignore',invalid='ignore'):
            for n,(i,k,l) in enumerate(self._triangles):
                good=ok[:,i]&ok[:,k]&ok[:,l];count[n]=good.sum()
                y=x[good].astype(np.complex128,copy=False)
                z1=y[:,:,i]*y[:,:,k].conj();z2=y[:,:,k]*y[:,:,l].conj();z3=y[:,:,l]*y[:,:,i].conj()
                a[:,n,:]=np.stack((z1.sum(axis=0),z2.sum(axis=0),z3.sum(axis=0)),axis=-1)
                h[:,n,:]=np.stack(((z1*z2).sum(axis=0),(z1*z3).sum(axis=0),(z2*z3).sum(axis=0)),axis=-1)
                j[:,n]=(z1*z2*z3).sum(axis=0)
            next_a=self._a+a;next_h=self._h+h;next_j=self._j+j
        next_count=self._counts+count
        if np.any(next_count>1000000) or self._nominal+len(x)>1000000000:
            raise ValueError('common sample count or nominal block count outside supported range')
        if not all(np.isfinite(v).all() for v in (next_a,next_h,next_j)):
            raise ValueError('bispectrum sums outside supported numerical range')
        self._a=next_a;self._h=next_h;self._j=next_j;self._counts=next_count
        self._nominal+=len(x);self._maximum_chunk=max(self._maximum_chunk,len(x));self._mask_supplied|=valid is not None

    def finish(self):
        if self._finished:raise ValueError('accumulator already finished')
        m=self._counts.astype(float);eligible=self._counts>=3
        with np.errstate(over='ignore',invalid='ignore'):
            product=np.prod(self._a,axis=-1)
            numerator=(product-self._h[:,:,0]*self._a[:,:,2]-self._h[:,:,1]*self._a[:,:,1]
                       -self._h[:,:,2]*self._a[:,:,0]+2*self._j)
            ordinary=np.divide(product,m**3,out=np.zeros_like(product),where=m>0)
            u=np.divide(numerator,m*(m-1)*(m-2),out=np.zeros_like(product),where=eligible)
        if not np.isfinite(ordinary).all() or not np.isfinite(u).all():raise ValueError('bispectrum output outside supported numerical range')
        self._finished=True
        return {'triangles':self._triangles.copy(),'common_sample_count':self._counts.copy(),
            'edge_sums':self._a.copy(),'paired_edge_sums':self._h.copy(),'triple_edge_sum':self._j.copy(),
            'paired_edge_order':'ab, ac, bc','ordinary_common_sample_product':ordinary,
            'distinct_sample_bispectrum':u,'distinct_sample_available':eligible.copy(),
            'nominal_blocks_seen':self._nominal,'maximum_chunk_blocks':self._maximum_chunk,
            'input_mask_supplied':self._mask_supplied,'input_sample_independence_verified':False,
            'input_mask_independence_verified':False,'generating_truth_used':False,
            'closure_phase_unbiased_guarantee':False,'production_visibility_statistics_changed':False,
            'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False}
