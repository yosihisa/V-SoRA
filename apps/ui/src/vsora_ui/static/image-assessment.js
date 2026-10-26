"use strict";
function renderImageAssessment(box,job){
  const info=job.image_assessment;if(!info)return;
  const panel=node("section",undefined,"image-assessment");panel.id="image-assessment-panel";
  panel.append(node("h3","画像結果の三つの判定"));
  if(info.state!=="available"){
    panel.append(node("p","画像評価の記録を確認できません。収束や画質の成功として扱わず、保存した記録を確認してください。","muted"));
  }else{
    const a=info.assessment,ref=a.reference_fidelity;
    const processing={queued:"実行待ち",running:"処理中",complete:"処理完了",failed:"失敗",cancelled:"中止",interrupted:"中断"};
    const numerical={converged:"収束",not_converged:"未収束",not_run:"未実行"};
    const grid=node("div",undefined,"metric-grid");
    grid.append(metric("処理の状態",processing[info.job_state]||"記録を確認"),metric("選択された探索",numerical[a.numerical.state]||"未評価"));
    grid.append(metric("参照画像との差",ref.state==="evaluated"?"NRMSE "+ref.registered_nrmse.toPrecision(4):"参照なし・未評価"));panel.append(grid);
    panel.append(node("p","処理完了、数値収束、参照画像との差は別の判定です。収束だけで画像の正しさは決まりません。","muted"));
    if(a.image_computed)panel.append(node("p","画像計算の記録あり。phase / amplitudeの独立制約数："+a.independent_constraints.phase+" / "+a.independent_constraints.logamp+"。","muted"));
    else panel.append(node("p","この記録には最終RML画像の計算結果がありません。","muted"));
    if(info.reference_note==="legacy_reference_record")panel.append(node("p","旧形式の参照値は、現在の全支持領域による評価として表示していません。","muted"));
    if(info.reference_note==="invalid_reference_record")panel.append(node("p","参照比較の記録が不正なため、形状の差は未評価です。","muted"));
  }
  const link=node("a","画像評価JSONを保存","download-link");link.href="/api/jobs/"+encodeURIComponent(job.id)+"/image-assessment";link.classList.add("image-assessment-download");panel.append(link);box.append(panel);
}
