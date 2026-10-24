"use strict";
function renderPhaseTemplate(box,s){
  const n=v=>v===null?"未解決":v.toExponential(6);
  const prediction=v=>v===null?"未解決":v?"Cas A":"点源";
  const header=(table,labels)=>{const row=node("tr");for(const label of labels)row.append(node("th",label));table.append(row);};
  box.append(node("h3","同じ電圧で局位相の既知・未知を比較"),
    node("p","8局 / 1.42GHz / 最大600m / 仮定flux1000Jy（零天空は0Jy）。固定7条件・各生成ラベル64区間。二つの方法は同じ電圧を使います。"),
    node("p","真値ありの参照だけに真の局位相を与え、位相探索へは渡しません。両方とも振幅・SEFD・二つの天空候補は既知です。未知振幅・SEFD・LOや画像を推定した結果ではありません。","muted"),
    node("p","区間内の局位相は一定、区間間は独立に引く模擬条件です。Mは独立Gaussian標本数の仮定、SEFDも仮定値で、実FFT独立性・実OCXOの変動・実感度を測った値ではありません。","muted"),
    node("p","scoreが正ならCas A、0以下なら点源と事前固定しています。位相探索後の最適な閾値や大域解は保証しません。低感度での判定の偏りを、実観測の画像化不可能性へ読み替えないでください。","muted"),
    node("p","正答率は二群を等しく平均した値、AUROCは順位指標です。個別95%区間は固定した生成条件と判定手順の二項誤り率の区間で、全条件同時の保証・画像の信頼区間ではありません。AUCの比較対を独立標本とは扱いません。","muted"),
    node("p","未収束を0点や除外へ置き換えません。未解決がある条件の探索側全体指標は未算出です。探索状態は真の局位相の同定を意味しません。現在のClosure＋RMLへの適用はありません。","muted"));
  const wrap=node("div",undefined,"raw-normalization-scroll phase-template-scroll"),table=node("table",undefined,"window-table");table.id="phase-template-summary-table";
  header(table,["条件・仮定","真値ありの参照","位相を探索","点源→Cas Aの誤り","Cas A→点源の誤り","未解決・対の予測表"]);
  for(const c of s.cases){
    const row=node("tr"),id=node("td");id.append(node("p",c.case_id),node("p","M："+c.modes.toLocaleString("ja-JP")),node("p","SEFD（Jy）："+n(c.sefd_jy)),node("p",c.zero_sky_control?"零天空・同一候補の対照":"既知点源・Cas A"));row.append(id);
    for(const key of ["oracle","phase_profile"]){const m=c.metrics[key],cell=node("td");cell.append(node("p","正答率："+n(m.balanced_accuracy)),node("p","AUROC："+n(m.empirical_auroc)));row.append(cell);}
    for(const role of ["false_casa_on_point","missed_casa"]){const cell=node("td");for(const [label,key] of [["真値あり","oracle"],["探索","phase_profile"]]){const r=c.metrics[key][role];if(r===null){cell.append(node("p",label+"：未解決のため未算出"));continue;}cell.append(node("p",label+" 件数："+r.errors+" / "+r.trials),node("p",label+" 誤り率："+n(r.fraction)),node("p",label+" 個別95%区間："+n(r.clopper_pearson_interval[0])+"〜"+n(r.clopper_pearson_interval[1])));}row.append(cell);}
    const cell=node("td");cell.append(node("p","未解決："+c.unresolved_profile_windows+" / "+(2*c.test_per_label)));
    for(const [label,key] of [["点源群","point_generation"],["Cas A群","casa_generation"]]){const m=c[key].oracle_by_profile_prediction_counts_on_resolved_only;cell.append(node("p",label+"："+m[0].join(" / ")+" ; "+m[1].join(" / ")));}row.append(cell);table.append(row);
  }
  wrap.append(table);box.append(node("p","表内を横にスクロールできます。対の予測表は受理区間だけで、行が真値あり、列が探索、各軸の順は点源・Cas Aです。未解決件数も併記します。","muted"),wrap);
  const details=node("details"),select=node("select"),label=node("label","詳しい区間を表示する条件"),detailWrap=node("div",undefined,"raw-normalization-scroll phase-template-scroll phase-template-detail"),detailTable=node("table",undefined,"window-table");
  select.id="phase-template-case";detailTable.id="phase-template-detail-table";
  for(const c of s.cases){const option=node("option",c.case_id+" / M"+c.modes.toLocaleString("ja-JP"));option.value=c.case_id;select.append(option);}
  label.append(select);details.append(node("summary","同じ区間の二つのscoreと判定"),label,node("p","区間番号は0始まりです。scoreは log[L(Cas A)/L(点源)] の向きです。探索側は局所的に合わせた候補の差で、画像確率や検定p値ではありません。零天空の対照では両scoreが0となり、同点規則で点源判定になります。全score・seed・条件をJSONで取得できます。","muted"));
  function show(){
    detailTable.replaceChildren();header(detailTable,["生成ラベル","区間番号（0始まり）","真値ありscore","位相探索score","真値ありの判定","探索の判定","探索状態","正誤"]);
    const c=s.cases.find(c=>c.case_id===select.value);
    for(const [name,key,isCasa] of [["点源群","point_generation",false],["Cas A群","casa_generation",true]])for(const r of c[key].rows){
      const row=node("tr"),state=r.profile_state==="not_converged"?"未収束":r.fit_states.every(v=>v==="phase_independent")?"位相依存なし":"局所停留候補";
      const correct=v=>v===null?"未解決":v===isCasa?"正答":"誤判定";
      for(const value of [name,String(r.window_index),n(r.oracle_score),n(r.phase_profile_score),prediction(r.oracle_prediction_casa),prediction(r.profile_prediction_casa),state,"真値あり："+correct(r.oracle_prediction_casa)+" / 探索："+correct(r.profile_prediction_casa)])row.append(node("td",value));detailTable.append(row);
    }
  }
  select.addEventListener("change",show);show();detailWrap.append(detailTable);details.append(detailWrap);box.append(details);
}
