"""Finite deterministic Cas A sensitivity grid; no real receiver inference."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_simulator.sensitivity import sefd_from_area,dish_area,information_plan
from vsora_observation import load_config
from workflows.compare_arrays import layout


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True);rows=[]
    for sefd in [1000,10000,100000,1000000]:
        config=load_config(Path(__file__).resolve().parents[1]/'configs/experiments/ideal-point.json')
        config['source']['model']='casa';config['observation'].update(duration_s=14400,integration_s=120)
        config['stations']=[{'id':f'ST{i+1:02d}','enu_m':p,'sefd_jy':sefd} for i,p in enumerate(layout(8,'spread'))]
        for exposure in [.1,.3,1.,3.]:
            for bandwidth in [256000.,2048000.]:
                result=information_plan(config,integration_s=exposure,bandwidth_hz=bandwidth)
                rows.append({'sefd_jy':sefd,'integration_s':exposure,'bandwidth_per_closure_channel_hz':bandwidth,
                   'expected_maximum_snr':result['expected_baseline_snr']['maximum'],
                   'independent_closure_counts':result['independent_closure_counts'],
                   'connected_snapshots':result['high_snr_connected_snapshots'],
                   'residual_rate_hz_for_90pct_coherence':result['maximum_residual_baseline_rate_hz_for_90pct_coherence']})
    examples=[{'diameter_m':d,'temperature_k':t,'aperture_efficiency':.6,
        'sefd_jy':sefd_from_area(t,dish_area(d,.6))} for d in [1.,3.,6.] for t in [50.,100.,300.]]
    summary={'type':'sensitivity_grid','rows':rows,'dish_assumptions':examples,
        'required_diameter_m_for_100K_efficiency06':{str(s):float(np.sqrt(8*1380.649*100/(np.pi*.6*s))) for s in [1000,10000,100000]},
        'limits':'Noiseless expected SNR counts, source total power included; no random detectability/LO-search/image success. 2.048 MHz assumes a single coherent closure channel and is an optimistic bandwidth comparison, not current 256 kHz VDIF performance.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for ax,bw in zip(axes,[256000.,2048000.]):
        for t in [.1,.3,1.,3.]:
            subset=[r for r in rows if r['integration_s']==t and r['bandwidth_per_closure_channel_hz']==bw]
            ax.semilogx([r['sefd_jy'] for r in subset],[r['independent_closure_counts']['logamp'] for r in subset],'o-',label=f'{t:g} s')
        ax.set(title=f'{bw/1e6:g} MHz / coherent channel',xlabel='Assumed SEFD (Jy)',ylabel='Expected independent amplitude closures')
        ax.grid(alpha=.2);ax.legend()
    fig.tight_layout();fig.savefig(out/'sensitivity-grid.png',dpi=140);plt.close(fig);return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(run(a.output),indent=2))
