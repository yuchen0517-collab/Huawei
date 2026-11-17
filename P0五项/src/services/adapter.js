// 提交适配层：mock 与 http 同一签名，切换只改一处。
// 对接既有任务（第 5 天）：统一错误格式 { error, detail }，六个错误码，前端只展示不解释。

export const ERROR_CATALOG = {
  INVALID_ACTION: '所选策略超出可用行动点，或与已锁定条款冲突。请调整选择后重新提交。',
  SESSION_BUSY: '上一轮仍在处理，本次提交被拒绝。已选卡牌完整保留，3 秒后自动重试。',
  MODEL_UNAVAILABLE: '谈判 Agent 本轮未返回结果。系统不会伪造对方行动或收益数据。',
  ROUND_LOCKED: '谈判已进入协议审计阶段，本轮不再接受新的策略出牌。',
  VERSION_CONFLICT: '对方刚刚更新了条款，你当前的选择已过期，不能覆盖对方最新行动。',
  TIMEOUT: '15 秒内未收到响应，请求可能仍在服务端处理。重试沿用同一 action_id。'
};

const config = {
  mode: 'mock', // 'mock' | 'http'
  httpBase: '',
  sessionId: 'sess-local-01'
};

let injected = null;

export function configure(next = {}) {
  Object.assign(config, next);
}

export function injectError(code) {
  injected = ERROR_CATALOG[code] ? code : null;
}

export function peekInjected() {
  return injected;
}

export function adapterId() {
  return config.mode;
}

function errorOf(code, payload, extra = {}) {
  return {
    ok: false,
    error: Object.assign({ error: code, detail: ERROR_CATALOG[code] }, extra)
  };
}

// mock：按注入的错误码返回失败，否则版本 +1 成功。
// 注意：注入是一次性的，演示时不会连坐后面的正常提交。
function mockSubmit(payload) {
  const code = injected;
  return new Promise(resolve => {
    const delay = code === 'TIMEOUT' ? 1600 : code ? 780 : 620;
    setTimeout(() => {
      if (code) {
        injected = null;
        const extra = {};
        if (code === 'SESSION_BUSY') extra.retryAfter = 3;
        if (code === 'VERSION_CONFLICT') extra.serverVersion = (payload.version || 1) + 1;
        resolve(errorOf(code, payload, extra));
        return;
      }
      resolve({ ok: true, patch: { version: (payload.version || 1) + 1 } });
    }, delay);
  });
}

// http：后端地址为空时诚实降级，不臆造成功（对齐第 6 天 httpAdapter 的做法）。
async function httpSubmit(payload) {
  if (!config.httpBase) {
    return errorOf('MODEL_UNAVAILABLE', payload, {
      detail: '未配置后端地址（httpBase 为空），本次不做假成功处理。'
    });
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${config.httpBase}/session/${config.sessionId}/action`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': payload.actionId
      },
      body: JSON.stringify({
        action_id: payload.actionId,
        round: payload.round,
        version: payload.version,
        strategy_ids: payload.strategyIds,
        base_action: payload.baseAction
      }),
      signal: controller.signal
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = body.error || 'INVALID_ACTION';
      return {
        ok: false,
        error: {
          error: code,
          detail: body.detail || ERROR_CATALOG[code] || '服务端拒绝了本次提交。',
          serverVersion: body.version,
          retryAfter: body.retry_after
        }
      };
    }
    return { ok: true, patch: { version: body.version } };
  } catch (err) {
    const aborted = err && err.name === 'AbortError';
    return errorOf('TIMEOUT', payload, {
      detail: aborted ? ERROR_CATALOG.TIMEOUT : '网络异常，重试沿用同一 action_id，不会产生第二笔行动。'
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function submitAction(payload) {
  return config.mode === 'http' ? httpSubmit(payload) : mockSubmit(payload);
}
