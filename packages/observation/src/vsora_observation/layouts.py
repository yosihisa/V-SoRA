"""Synthetic reference station layouts with an explicit maximum pair distance."""
import numbers
import numpy as np


def reference_layout(stations,kind,maximum_baseline_m=600.):
    if isinstance(stations,bool) or not isinstance(stations,(int,np.integer)) or stations not in (4,8):raise ValueError('reference4/8station layout required')
    if not isinstance(kind,str) or kind not in ('spread','line','ring'):raise ValueError('reference spread/line/ring layout required')
    if (np.ma.isMaskedArray(maximum_baseline_m) or isinstance(maximum_baseline_m,(bool,np.bool_))
        or not isinstance(maximum_baseline_m,numbers.Real) or not np.isfinite(maximum_baseline_m)
        or not 10<=maximum_baseline_m<=600):raise ValueError('finite maximum pair distance[10,600] metres required')
    maximum=float(maximum_baseline_m)
    if kind=='line':return np.c_[np.linspace(-maximum/2,maximum/2,stations),np.zeros((stations,2))]
    if kind=='ring':
        angle=np.arange(stations)*2*np.pi/stations
        return np.c_[maximum/2*np.cos(angle),maximum/2*np.sin(angle),np.zeros(stations)]
    points=np.array([[-200,-130,0],[-180,-100,0],[160,-180,0],[220,170,0],[-240,160,0],[-40,40,0],[40,-80,0],[180,20,0]],float)[:stations]
    return points*maximum/np.linalg.norm(points[:,None]-points[None,:],axis=-1).max()
