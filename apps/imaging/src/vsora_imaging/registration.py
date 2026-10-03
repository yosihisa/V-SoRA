"""Translation-only, zero-extended image comparison with retained full support.

All integer cells in a bounded translation square are covered. Each bilinear
cell is refined by deterministic multistart coordinate minimization; this is
numerical coverage, not a proof of the exact continuous global minimum.
"""
import numpy as np
from scipy.ndimage import shift
from scipy.signal import fftconvolve


def register_translation(a,b,max_shift_pixels):
    a=np.asarray(a,float);b=np.asarray(b,float)
    if (a.ndim!=2 or a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all()
            or isinstance(max_shift_pixels,bool) or not isinstance(max_shift_pixels,int) or not 0<=max_shift_pixels<=127):
        raise ValueError('finite matching images and integer translation bound 0..127 required')
    if max_shift_pixels==0:
        return b.copy(),{'shift_yx_pixels':[0.,0.],'boundary_reached':False,'grid_cells':1,
                         'multistarts_per_cell':1,'selected_coordinate_converged':True,'objective_identity_error':0.}
    limit=max_shift_pixels;cross=fftconvolve(a,b[::-1,::-1],mode='full')
    auto=fftconvolve(b,b[::-1,::-1],mode='full');center=np.array(a.shape)-1
    if np.any(center<limit+1):raise ValueError('images must have enough padding for requested translations')
    corners=np.array([[0,0],[1,0],[0,1],[1,1]])
    gram=np.empty((4,4))
    for i,left in enumerate(corners):
        for j,right in enumerate(corners):gram[i,j]=auto[tuple(center+left-right)]
    yy,xx=np.meshgrid(np.arange(-limit,limit),np.arange(-limit,limit),indexing='ij')
    origins=np.stack([yy.ravel(),xx.ravel()],axis=1)
    c=np.stack([cross[origins[:,0]+corner[0]+center[0],origins[:,1]+corner[1]+center[1]] for corner in corners],axis=1)
    norm=float(np.sum(a*a));best={'error':np.inf}
    def weights(u,v):return np.stack([(1-u)*(1-v),u*(1-v),(1-u)*v,u*v],axis=1)
    def quadratic_coordinate(base,delta):
        den=np.einsum('ij,jk,ik->i',delta,gram,delta)
        numerator=np.einsum('ij,ij->i',c,delta)-np.einsum('ij,jk,ik->i',delta,gram,base)
        return np.clip(np.divide(numerator,den,out=np.zeros_like(den),where=den>np.finfo(float).eps*max(gram[0,0],1e-100)),0,1)
    for initial_u in [0.,.5,1.]:
        for initial_v in [0.,.5,1.]:
            u=np.full(len(origins),initial_u);v=np.full(len(origins),initial_v)
            change=np.full(len(origins),np.inf)
            for iteration in range(100):
                old_u,old_v=u.copy(),v.copy();zero=np.zeros_like(v)
                base=np.stack([1-v,zero,v,zero],axis=1);delta=np.stack([-(1-v),1-v,-v,v],axis=1)
                u=quadratic_coordinate(base,delta)
                base=np.stack([1-u,u,zero,zero],axis=1);delta=np.stack([-(1-u),-u,1-u,u],axis=1)
                v=quadratic_coordinate(base,delta)
                change=np.maximum(abs(u-old_u),abs(v-old_v))
                if change.max()<1e-8:break
            w=weights(u,v);error=norm+np.einsum('ij,jk,ik->i',w,gram,w)-2*np.einsum('ij,ij->i',w,c)
            index=int(np.argmin(error))
            if error[index]<best['error']:
                best={'error':float(error[index]),'offset':origins[index]+[u[index],v[index]],
                      'converged':bool(change[index]<1e-7),'iterations':iteration+1}
    offset=best['offset'];registered=shift(b,offset,order=1,mode='constant',cval=0.,prefilter=False)
    actual=float(np.sum((registered-a)**2));identity=abs(actual-best['error'])
    if identity>1e-9*max(norm,float(np.sum(b*b)),1e-100):
        raise ValueError('registration padding loses image support')
    return registered,{'shift_yx_pixels':offset.tolist(),'boundary_reached':bool(np.any(abs(offset)>=limit-1e-5)),
        'grid_cells':len(origins),'multistarts_per_cell':9,'selected_coordinate_converged':best['converged'],
        'selected_coordinate_iterations':best['iterations'],'objective_identity_error':identity}
