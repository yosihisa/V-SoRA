"""同じ参照で、外部RMLの局所勾配と反復上限を診断する。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflows.ehtim_image_reference import external_problem,external_imager,capture_minimize,sha


def directional_gradient(function,gradient,point,*,seed=124,directions=5):
    """三つの固定stepの中心差分を記録。主判定はh=1e-4の局所方向微分。"""
    x=np.asarray(point,dtype=float)
    if x.ndim!=1 or not len(x) or not np.isfinite(x).all() or type(directions) is not int or directions<1:raise ValueError('finite vector and positive direction count required')
    original=x.copy();g=np.asarray(gradient(x.copy()),dtype=float)
    if g.shape!=x.shape or not np.isfinite(g).all():raise ValueError('finite matching analytic gradient required')
    rng=np.random.default_rng(seed);rows=[]
    for index in range(directions):
        d=rng.normal(size=len(x));d/=np.linalg.norm(d);analytic=float(g@d);steps=[]
        for h in [.001,.0001,.00001]:
            plus=float(function(x+h*d));minus=float(function(x-h*d))
            if not np.isfinite([plus,minus]).all():raise ValueError('nonfinite finite-difference objective')
            estimate=(plus-minus)/(2*h);error=abs(estimate-analytic)/max(1.,abs(estimate),abs(analytic))
            steps.append({'h':h,'analytic_directional':analytic,'central_difference':estimate,'normalized_error':float(error)})
        extrapolated=(100*steps[2]['central_difference']-steps[1]['central_difference'])/99
        secondary=abs(extrapolated-analytic)/max(1.,abs(extrapolated),abs(analytic))
        rows.append({'direction':index,'steps':steps,'primary_passed':steps[1]['normalized_error']<=1e-5,
            'secondary_richardson_directional':float(extrapolated),'secondary_normalized_error':float(secondary)})
    np.testing.assert_array_equal(x,original)
    return {'directions':rows,'primary_step':.0001,'normalized_tolerance':1e-5,'all_primary_passed':all(x['primary_passed'] for x in rows),
        'maximum_primary_normalized_error':max(x['steps'][1]['normalized_error'] for x in rows),'maximum_secondary_normalized_error':max(x['secondary_normalized_error'] for x in rows),'gradient_maximum_absolute_component':float(np.max(abs(g))),
        'scope':'finite local states, directions and steps only; not a global derivative proof'}


def run(reference,output):
    reference=Path(reference);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    problem=external_problem(reference);metadata,data,observations,channels,image_object=problem
    initial_input_sha=sha(reference/'input.npz');limits=[]
    for limit in [2000,5000]:
        directory=out/f'iterations-{limit}';directory.mkdir();runs=[];models=[]
        for start,image in enumerate(data['initial_images']):
            imager=external_imager(problem,image,limit)
            if not hasattr(imager,'_xinit'):imager.init_imager()
            initial=imager._xinit.copy();before=directional_gradient(imager.objfunc,imager.objgrad,initial)
            result,records,inputs=capture_minimize(lambda:imager.make_image(pol='I',show_updates=False),1)
            np.testing.assert_array_equal(inputs[0],initial)
            after=directional_gradient(imager.objfunc,imager.objgrad,imager.tmpout)
            np.testing.assert_allclose(imager.objfunc(imager.tmpout),records[0]['objective'],rtol=1e-12,atol=1e-10)
            raw=result.imvec.reshape(8,8)[::-1,::-1].copy()
            if not np.isfinite(raw).all() or np.any(raw<0) or raw.sum()<=0:raise ValueError('invalid external relative image')
            q=raw/raw.sum();models.append(q);np.save(directory/f'start-{start}.npy',q)
            runs.append({'start':start,**records[0],'initial_gradient':before,'final_gradient':after,'image_flux_before_gauge_normalization':float(raw.sum()),
                'initial_image_maximum_difference':float(np.max(np.abs(np.exp(initial).reshape(8,8)[::-1,::-1]-image)))})
            print(json.dumps({'limit':limit,'start':start,'optimizer_success':records[0]['optimizer_success'],'gradient_passed':before['all_primary_passed'] and after['all_primary_passed']}),flush=True)
        selected=int(np.argmin([x['objective'] for x in runs]));np.save(directory/'relative-model.npy',models[selected])
        science={'state':'complete','method':'ehtim1.3.2','max_iterations':limit,'selected_start':selected,'runs':runs,'input_sha256':initial_input_sha,
            'image_sha256':sha(directory/'relative-model.npy'),'truth_used_for_settings_or_selection':False,'actual_observation_validated':False}
        (directory/'science.json').write_text(json.dumps(science,indent=2)+'\n');limits.append(science)
    assert sha(reference/'input.npz')==initial_input_sha
    result={'stage':124,'state':'complete','limits':limits,'gradient_states':12,'directions_per_state':5,'steps_per_direction':3,'input_sha256':initial_input_sha,
        'all_local_primary_gradient_checks_passed':all(state['all_primary_passed'] for row in limits for run in row['runs'] for state in [run['initial_gradient'],run['final_gradient']]),
        'cited_stage123_max_iterations':800,'reference_metadata_unchanged':True,'actual_observation_validated':False}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.reference,a.output)
