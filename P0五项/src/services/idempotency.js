// 幂等键：一个「提交意图」对应一个 action_id。
// 规则（对齐第 5 天）：草稿不变则重试沿用同一 id；选卡一变即作废重新生成。

let actionId = null;
let signature = '';

export function actionIdFor(nextSignature) {
  if (actionId && signature === nextSignature) return actionId;
  signature = nextSignature;
  actionId = `act_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  return actionId;
}

export function consumeActionId() {
  const current = actionId;
  actionId = null;
  signature = '';
  return current;
}

export function peekActionId() {
  return actionId;
}
