"""Conditional whole-window sign invariance, finite vector experiments only."""
import json
from pathlib import Path
import numpy as np
from vsora_imaging.window_symmetry import exact_window_sign_flip_test

MODELS=('normal_full_rank','normal_shared_features','student_t3_shared_scale')
COUNTS=(1,4,8,12)


def experiment(model,windows,trials=4096,seed=86):
 if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=16384:raise ValueError('integer trials1024..16384 required')
 if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2**32-1:raise ValueError('integer seed0..2^32-1 required')
 if isinstance(windows,bool) or not isinstance(windows,int) or windows not in COUNTS:raise ValueError('fixed windows1/4/8/12 required')
 if model not in MODELS+('shared_windows_counterexample',):raise ValueError('fixed vector model required')
 rng=np.random.default_rng(seed);features=4
 if model=='normal_shared_features':
  values=rng.normal(size=(trials,windows,1))*np.array([1.,.5,-.75,2.])
 elif model=='student_t3_shared_scale':
  values=rng.normal(size=(trials,windows,features))/np.sqrt(rng.chisquare(3,size=(trials,windows,1))/3)
 elif model=='shared_windows_counterexample':
  values=np.repeat(rng.normal(size=(trials,1,features)),windows,axis=1)
 else:values=rng.normal(size=(trials,windows,features))
 results=[exact_window_sign_flip_test(x) for x in values];p=np.array([r['upper_tail_p_value'] for r in results]);tails=[r['tail_count'] for r in results]
 valid=model!='shared_windows_counterexample';levels=[]
 for alpha in (.01,.05):
  count=int(np.count_nonzero(p<=alpha));fraction=count/trials;reference_se=float(np.sqrt(alpha*(1-alpha)/trials))
  levels.append({'nominal_level':alpha,'rejections':count,'fraction':fraction,'reference_binomial_mc_standard_error_at_nominal':reference_se,
                 'within_nominal_plus_6_reference_se':bool(fraction<=alpha+6*reference_se) if valid else None})
 expected=2/(1<<windows)
 return {'model':model,'windows':windows,'features':features,'trials':trials,'seed':seed,'joint_null_invariance_satisfied_by_generation':valid,
         'window_marginal_symmetry_in_generation':True,'whole_rows_flipped':True,'features_assumed_independent':False,
         'p_value_minimum':float(p.min()),'p_value_median':float(np.median(p)),'p_value_maximum':float(p.max()),
         'minimum_possible_two_sided_p':expected,'all_tail_counts_even_and_positive':all(n>=2 and n%2==0 for n in tails),
         'levels':levels,'all_counterexample_p_values_equal_minimum':bool(np.all(p==expected)) if not valid else None,
         'gaussian_p_value_approximation_used':False,'physical_voltage_generated':False}


def run(output,trials=4096):
 out=Path(output)
 if out.exists():raise FileExistsError('new sign-flip experiment output required')
 out.mkdir(parents=True)
 settings=[(m,q) for m in MODELS for q in COUNTS]+[('shared_windows_counterexample',8)]
 cases=[experiment(m,q,trials,86+n) for n,(m,q) in enumerate(settings)]
 passed=all(c['all_tail_counts_even_and_positive'] and (all(x['within_nominal_plus_6_reference_se'] for x in c['levels']) if c['joint_null_invariance_satisfied_by_generation'] else c['all_counterexample_p_values_equal_minimum']) for c in cases)
 result={'type':'whole_window_sign_flip_validation','state':'complete' if passed else 'failed_validation','trials_per_condition':trials,'cases':cases,
         'full_group_enumerated':True,'float64_tie_epsilon_multiplier':4096,'physical_voltage_generated':False,'adc_fft_vdif_processed':False,
         'source_or_shape_detection_claimed':False,'null_invariance_verified_for_observations':False,
         'production_rml_noise_model_changed':False,
         'scope':'Finite real-vector experiments and a deliberately dependent-window counterexample. Joint group invariance is a model assumption. Per-condition rejection fractions are not sky/image detection performance or a guarantee under empirical window selection.'}
 (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 plot(result,out/'window-sign-symmetry.png')
 if not passed:raise RuntimeError('fixed sign-flip null or counterexample check failed')
 return result


def plot(result,path):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,3,figsize=(14,4))
 for index,alpha in enumerate((.01,.05)):
  ax=axes[index]
  for model in MODELS:
   cases=[c for c in result['cases'] if c['model']==model]
   rates=[next(r['fraction'] for r in c['levels'] if r['nominal_level']==alpha) for c in cases]
   ax.plot([c['windows'] for c in cases],rates,'o-',label=model.replace('_',' '))
  ax.axhline(alpha,color='black',linestyle='--',label=f'Nominal {alpha:g}')
  ax.set(xlabel='Window vectors Q',ylabel='MC rejection fraction',title=f'Joint sign-invariant models, level {alpha:g}',xticks=COUNTS)
  ax.grid(alpha=.2)
 axes[0].legend(fontsize=6)
 baseline=next(c for c in result['cases'] if c['model']=='normal_full_rank' and c['windows']==8)
 counter=next(c for c in result['cases'] if c['model']=='shared_windows_counterexample')
 fractions=[next(r['fraction'] for r in c['levels'] if r['nominal_level']==.05) for c in (baseline,counter)]
 axes[2].bar(['Independent windows','Copied windows'],fractions,color=['C0','C3'])
 axes[2].axhline(.05,color='black',linestyle='--')
 axes[2].set(ylabel='MC rejection fraction at level0.05',title='Marginal symmetry alone is insufficient',ylim=(0,1.05))
 axes[2].tick_params(axis='x',labelsize=8)
 fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=4096)
 r=run(**vars(p.parse_args()));print(json.dumps({'state':r['state'],'conditions':len(r['cases'])}))


if __name__=='__main__':main()
