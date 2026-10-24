"use strict";
function renderKnownCovariance(box,s){
  const n=v=>v.toExponential(6);
  box.append(node("h3","既知共分散で点源とCas Aを比較"),
    node("p","8局 / 1.42GHz / 最大600m / 仮定flux1000Jy（零天空は0Jy）。固定9条件・各ラベル評価512、学習なし。"),
    node("p","局位相基準・電力・SEFDと二つの天空モデルを与えた参照計算です。未知gain・SEFD・LOを推定した結果ではありません。天空位置の自由度が残るClosure画像化とは条件が異なります。","muted"),
    node("p","SEFDは仮定値です。1m・100K・効率0.6の値も計算例で、実測値ではありません。M19200は64kHz×0.3秒の理想mode数で、実FFTの独立性を測った値ではありません。","muted"),
    node("p","対数尤度比が0より大きいとCas A、0以下は点源です。評価データで閾値やモデルを選び直していません。正答率は二群を等しく平均した値、AUROCは順位指標です。","muted"),
    node("p","個別95%区間は固定した既知モデルの下での二項誤判定率です。全条件同時の保証・画像の信頼区間ではありません。誤り0でも将来のリスク0を保証しません。現在のRMLへの適用はありません。","muted"));
  function header(table,labels){const row=node("tr");for(const label of labels)row.append(node("th",label));table.append(row);}
  const wrap=node("div",undefined,"raw-normalization-scroll gaussian-template-scroll"),table=node("table",undefined,"window-table");table.id="gaussian-template-summary-table";
  header(table,["条件・mode数","SEFD（Jy、仮定と生成）","正答率・AUROC（0〜1）","点源→Cas Aの誤り","Cas A→点源の誤り"]);
  for(const c of s.cases){
    const row=node("tr"),id=node("td"),sefd=node("td"),metric=node("td");
    id.append(node("p",c.case_id),node("p","M："+c.modes.toLocaleString("ja-JP")),node("p",c.zero_sky_control?"零天空・同一候補の対照":c.receiver_model_matches_generation?"受信機モデル一致":"受信機モデル誤指定"));
    sefd.append(node("p","仮定："+n(c.assumed_receiver_sefd_jy)),node("p","点源生成："+n(c.point_generated_sefd_jy)),node("p","Cas A生成："+n(c.casa_generated_sefd_jy)));
    metric.append(node("p","正答率："+n(c.balanced_accuracy)),node("p","AUROC："+n(c.empirical_auroc)));row.append(id,sefd,metric);
    for(const r of [c.false_casa_on_point,c.missed_casa]){
      const cell=node("td");cell.append(node("p","件数："+r.errors+" / "+r.trials),node("p","誤り率："+n(r.fraction)),node("p","個別95%区間："+n(r.clopper_pearson_interval[0])+"〜"+n(r.clopper_pearson_interval[1])));row.append(cell);
    }
    table.append(row);
  }
  wrap.append(table);box.append(node("p","表内を横にスクロールできます。誤指定は片方の生成雑音を意図的に変えた人工対照です。高い正答率も実観測の保証ではありません。","muted"),wrap);
  const details=node("details"),select=node("select"),label=node("label","詳しい評価区間を表示する条件"),detailWrap=node("div",undefined,"raw-normalization-scroll gaussian-template-scroll gaussian-template-detail"),detailTable=node("table",undefined,"window-table");
  select.id="gaussian-template-case";detailTable.id="gaussian-template-detail-table";
  for(const c of s.cases){const option=node("option",c.case_id+" / M"+c.modes.toLocaleString("ja-JP"));option.value=c.case_id;select.append(option);}
  label.append(select);details.append(node("summary","評価区間ごとの尤度比と判定"),label,
    node("p","区間番号は0始まりです。零天空の対照では、点源群とCas A群の生成分布は同じです。同点0を点源とするので、二群の誤り率は0と1になります。表内を縦・横にスクロールできます。全score・共分散・seedはsummary.jsonで取得できます。","muted"));
  function show(){
    detailTable.replaceChildren();header(detailTable,["評価ラベル","区間番号（0始まり）","対数尤度比 log[L(Cas A)/L(点源)]","固定閾値0の判定","正誤"]);
    const c=s.cases.find(c=>c.case_id===select.value);
    for(const [name,key,isCasa] of [["点源群","point_test_log_likelihood_ratios",false],["Cas A群","casa_test_log_likelihood_ratios",true]]){
      c[key].forEach((score,index)=>{const predicted=score>0,row=node("tr");
        row.append(node("td",name),node("td",String(index)),node("td",n(score)),node("td",predicted?"Cas A":"点源"),node("td",predicted===isCasa?"正答":"誤判定"));detailTable.append(row);});
    }
  }
  select.addEventListener("change",show);show();detailWrap.append(detailTable);details.append(detailWrap);box.append(details);
}
