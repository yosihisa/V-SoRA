"""Exact sufficient-statistic accumulation of nonoverlapping FX blocks."""
import numpy as np
from .quality import validate_quality
from .bispectrum_accumulator import BispectrumAccumulator


class FXAccumulator:
    def __init__(self,stations,sample_rate_hz,fft_length,center_frequency_hz,spectral_quality=None,collect_bispectrum=False):
        if not isinstance(stations,int) or stations<2 or not isinstance(fft_length,int) or fft_length<2 or sample_rate_hz<=0:
            raise ValueError('invalid streaming FX dimensions')
        if not isinstance(collect_bispectrum,bool):raise ValueError('collect_bispectrum bool required')
        self.bispectrum=BispectrumAccumulator(stations,fft_length) if collect_bispectrum else None
        self.stations=stations;self.fs=sample_rate_hz;self.nf=fft_length
        self.quality=validate_quality(spectral_quality) if spectral_quality is not None else None
        self.pairs=np.array([(i,j) for i in range(stations) for j in range(i+1,stations)])
        self.frequency=center_frequency_hz+np.fft.fftfreq(fft_length,1/sample_rate_hz)
        self.cross=np.zeros((fft_length,len(self.pairs)),complex);self.counts=np.zeros(len(self.pairs),np.int64)
        self.power=np.zeros((fft_length,stations));self.power2=np.zeros_like(self.power)
        self.station_counts=np.zeros(stations,np.int64);self.sample_power=np.zeros(stations);self.sample_counts=np.zeros(stations,np.int64)
        self.samples=0;self.maximum_chunk_samples=0;self.finished=False

    def consume(self,samples,valid=None):
        if self.bispectrum is not None and (np.ma.isMaskedArray(samples) or np.ma.isMaskedArray(valid)
                or (valid is not None and np.asarray(valid).dtype!=np.bool_)):
            raise ValueError('raw bispectrum requires unmasked samples and boolean validity')
        x=np.asarray(samples);ok=np.ones(x.shape,bool) if valid is None else np.asarray(valid,bool)
        if (self.finished or x.ndim!=2 or len(x)!=self.stations or x.shape[1]==0 or x.shape[1]%self.nf
            or not np.iscomplexobj(x) or not np.isfinite(x).all() or ok.shape!=x.shape):
            raise ValueError('finite complete FFT blocks required before finish')
        block_ok=ok.reshape(self.stations,-1,self.nf).all(axis=2).T
        spectrum=np.fft.fft(x.reshape(self.stations,-1,self.nf).transpose(1,2,0),axis=1,norm='ortho')
        if self.bispectrum is not None:self.bispectrum.consume(spectrum,block_ok)
        self.samples+=x.shape[1];self.maximum_chunk_samples=max(self.maximum_chunk_samples,x.shape[1])
        for s in range(self.stations):
            p=abs(spectrum[block_ok[:,s],:,s])**2
            self.station_counts[s]+=len(p);self.power[:,s]+=p.sum(axis=0);self.power2[:,s]+=(p*p).sum(axis=0)
            self.sample_power[s]+=(abs(x[s,ok[s]])**2).sum();self.sample_counts[s]+=ok[s].sum()
        for b,(i,j) in enumerate(self.pairs):
            good=block_ok[:,i]&block_ok[:,j]
            self.cross[:,b]+=(spectrum[good,:,i]*spectrum[good,:,j].conj()).sum(axis=0)
            self.counts[b]+=good.sum()

    def finish(self,time_offset_s=0.):
        if self.finished or not self.samples:raise ValueError('nonempty unfinished accumulator required')
        self.finished=True
        v=np.divide(self.cross,self.counts,out=np.zeros_like(self.cross),where=self.counts>0)
        total=np.divide(self.sample_power,self.sample_counts,out=np.zeros_like(self.sample_power),where=self.sample_counts>0)
        i,j=self.pairs.T;pairpower=total[i]*total[j];diagnostics={}
        if self.quality is not None:
            q=self.quality;power=np.divide(self.power,self.station_counts,out=np.zeros_like(self.power),where=self.station_counts>0)
            sk=np.ones_like(power);eligible=np.zeros_like(power,bool);reason=np.zeros_like(power,dtype=np.uint8)
            for s,m in enumerate(self.station_counts):
                positive=power[:,s]>0;reason[~positive,s]|=1
                if m>=q['min_sk_blocks']:
                    sk[positive,s]=(m+1)/(m-1)*(self.power2[positive,s]/m/power[positive,s]**2-1)
                    sk[:,s]=np.maximum(sk[:,s],0);eligible[positive,s]=True
                    reason[positive&(sk[:,s]<q['sk_bounds'][0]),s]|=2
                    reason[positive&(sk[:,s]>q['sk_bounds'][1]),s]|=4
            for lo,hi in q['exclude_rf_ranges_hz']:reason[(self.frequency>=lo)&(self.frequency<=hi),:]|=8
            diagnostics={'diagnostic_station_power':power,'diagnostic_station_sk':sk,
                'diagnostic_station_sk_eligible':eligible,'diagnostic_station_flags':reason,
                'diagnostic_station_valid_fft_count':self.station_counts.copy()}
            if q['channel_weights']:pairpower=power[:,i]*power[:,j]
        weight=np.divide(2*self.counts,pairpower,out=np.zeros_like(pairpower),where=pairpower>0)
        weight=np.broadcast_to(weight,v.shape).copy()
        if self.quality is not None:weight[(reason[:,i]!=0)|(reason[:,j]!=0)]=0
        order=np.argsort(self.frequency)
        result={**{k:(x if k.endswith('valid_fft_count') else x[order])[None] for k,x in diagnostics.items()},
            'vis_jy':v[order][None],'weights':weight[order][None],'pairs':self.pairs,
            'frequencies_hz':self.frequency[order],'times_s':np.array([time_offset_s+self.samples/(2*self.fs)]),
            'integration_s':(self.counts*self.nf/self.fs)[None],'valid_fft_count':self.counts[None].copy(),
            'noise_weight_assumption':('2*valid FFT blocks / product of measured station channel powers; weak-source quadrature approximation'
                if self.quality is not None and self.quality['channel_weights'] else '2*valid FFT blocks / product of measured station total powers')}

        if self.bispectrum is not None:
            raw=self.bispectrum.finish()
            for key in ('edge_sums','paired_edge_sums','triple_edge_sum','ordinary_common_sample_product','distinct_sample_bispectrum'):
                raw[key]=raw[key][order]
            pair_index={tuple(pair):n for n,pair in enumerate(self.pairs)}
            usable=np.broadcast_to(raw['distinct_sample_available'],(self.nf,len(raw['triangles']))).copy()
            for n,(i,j,k) in enumerate(raw['triangles']):
                indices=[pair_index[(i,j)],pair_index[(j,k)],pair_index[(i,k)]]
                usable[:,n]&=(result['weights'][0][:,indices]>0).all(axis=1)
            raw['channel_triangle_usable']=usable
            raw['frequencies_hz']=result['frequencies_hz'].copy()
            result['raw_bispectrum']=raw
        return result
