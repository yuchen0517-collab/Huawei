/**
 * 突发事件卡 · 视图层（纯渲染）
 * 输入事件对象 → 输出整张卡片的 HTML 字符串。无状态、无事件绑定、不触碰 DOM。
 * 数据契约见 domain.md「5.4 事件卡组件库」。
 * 来源：事件卡1.2(1)/事件卡1.2/event-card.js 的渲染部分，拆分为 ES Module。
 */
import { escapeHTML } from '../ui.js';
import artG01 from './art/G01.jpg';

export const EVENT_KINDS = { technology: '技术突变', scandal: '舆论风暴', conflict: '地缘危机', diplomacy: '外交动向', economy: '经济冲击', disaster: '突发灾难', interlude: '会场花絮' };
const INDEX_LABELS = { interest: '利益', image: '形象', trust: '信任' };

/**
 * 事件 id → 写真图。图片经 ESM 导入，
 * Vite 构建会输出带 hash 的资源文件，esbuild 单文件版会内联成 data URI。
 * 新增事件时在此登记一行即可；未登记的事件自动回退 SVG 兜底图。
 */
const ART_SRC = {
  G01: artG01
};

/** 取图优先级：event.art（显式指定） > ART_SRC[id] > null（走 SVG 兜底） */
export function artSource(event) {
  if (!event) return null;
  if (event.art) return String(event.art);
  const key = String(event.id || '').toUpperCase();
  return ART_SRC[key] || null;
}

function icon() { return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2L4 14h7l-1 8 10-13h-7z"/></svg>'; }

/** SVG 兜底插画：按事件类型绘制，图片缺失时可见。 */
function svgArt(kind) {
  if (kind === 'interlude') return svgArt('diplomacy');
  const defs = '<defs><linearGradient id="ec-bg" x2="1" y2="1"><stop stop-color="#111b2b"/><stop offset="1" stop-color="#27364b"/></linearGradient><linearGradient id="ec-gold" x2="0" y2="1"><stop stop-color="#f4d997"/><stop offset="1" stop-color="#a77b35"/></linearGradient><radialGradient id="ec-glow"><stop stop-color="#e5bd6d" stop-opacity=".42"/><stop offset="1" stop-color="#e5bd6d" stop-opacity="0"/></radialGradient></defs>';
  const base = defs + '<rect width="360" height="180" fill="url(#ec-bg)"/><path d="M0 155L360 105V180H0z" fill="#080d15" opacity=".35"/><circle cx="180" cy="85" r="105" fill="url(#ec-glow)"/>';
  if (kind === 'technology') return '<svg viewBox="0 0 360 180" aria-hidden="true">' + base + '<g fill="none" stroke="#72b7c4" stroke-width="1" opacity=".5"><path d="M0 42h70l20 20h45M0 122h62l25-25h38M360 40h-68l-22 22h-35M360 128h-72l-20-22h-38"/><circle cx="70" cy="42" r="3"/><circle cx="62" cy="122" r="3"/><circle cx="292" cy="40" r="3"/><circle cx="288" cy="128" r="3"/></g><g transform="translate(125 45)"><rect x="-12" y="12" width="134" height="76" rx="5" fill="#0b111d" stroke="#c9a061"/><rect width="110" height="100" rx="6" fill="#1d2c3c" stroke="#efd7a8" stroke-width="2"/><rect x="13" y="13" width="84" height="74" fill="#101a27" stroke="#658294"/><text x="55" y="62" text-anchor="middle" fill="#efd7a8" font-family="Georgia,serif" font-size="31" letter-spacing="4">AI</text><path d="M55 0v-13M28 0v-13M82 0v-13M55 100v13M28 100v13M82 100v13" stroke="#c9a061" stroke-width="3"/></g><g transform="translate(287 27)"><path d="M0 28L15 0l15 28z" fill="#d89a54" stroke="#ffe0a1"/><path d="M15 9v9" stroke="#1a202b" stroke-width="2"/><circle cx="15" cy="23" r="1.4" fill="#1a202b"/></g></svg>';
  if (kind === 'scandal') return '<svg viewBox="0 0 360 180" aria-hidden="true">' + base.replace('#27364b', '#4a2332') + '<g transform="translate(48 34) rotate(-7 80 60)"><rect width="142" height="116" fill="#e8dcc3" stroke="#9d8359"/><rect x="10" y="10" width="122" height="20" fill="#232b38"/><text x="71" y="25" text-anchor="middle" fill="#efd7a8" font-family="Georgia,serif" font-size="12" letter-spacing="3">LEAK</text><rect x="10" y="39" width="52" height="42" fill="#7b858b"/><path d="M70 42h60M70 50h60M70 58h48M10 90h120M10 99h120M10 108h83" stroke="#77694f" stroke-width="3"/></g><g transform="translate(251 40)" fill="none" stroke="#efbb87"><path d="M0 83L19 0l19 83M8 53h22M4 70h30" stroke-width="3"/><circle cx="19" cy="8" r="5" fill="#efbb87"/><path d="M2 20c-20 14-20 36 0 50M36 20c20 14 20 36 0 50M-8 9c-30 22-30 56 0 78M46 9c30 22 30 56 0 78" stroke-width="2" opacity=".75"/></g></svg>';
  if (kind === 'conflict') return '<svg viewBox="0 0 360 180" aria-hidden="true">' + base.replace('#27364b', '#493029') + '<g fill="#536154" stroke="#95a287" stroke-width="1" opacity=".85"><path d="M28 44l45-21 38 11 25-13 32 22-12 27-39 7-21 31-42-13-18-25zM212 91l28-29 39 5 18-18 42 24-9 42-33 29-49-8-28-20z"/></g><g fill="none" stroke="#efc367" stroke-width="2"><circle cx="118" cy="68" r="16"/><circle cx="118" cy="68" r="28" opacity=".45"/><path d="M118 32v20M118 84v20M82 68h20M134 68h20"/></g><path d="M54 139l93-51" stroke="#dc7b62" stroke-width="5"/><path d="M133 85l14 2-4 13" fill="none" stroke="#dc7b62" stroke-width="5"/><path d="M302 132l-93-49" stroke="#7fb0ca" stroke-width="5"/><path d="M223 82l-14 1 4 13" fill="none" stroke="#7fb0ca" stroke-width="5"/></svg>';
  if (kind === 'diplomacy') return '<svg viewBox="0 0 360 180" aria-hidden="true">' + base.replace('#27364b', '#23453f') + '<g transform="translate(48 26)"><path d="M15 0v125M255 0v125" stroke="#bda56e" stroke-width="4"/><path d="M18 5h70v48H18z" fill="#b84f49"/><path d="M182 5h70v48h-70z" fill="#526f9d"/><path d="M88 112l49-37 25 14 25-14 49 37-21 25-36-23h-28l-36 23z" fill="#d2b184" stroke="#f1d6a4"/><path d="M137 75l25 14 25-14" fill="none" stroke="#fff0c8" stroke-width="3"/><path d="M112 126l25-12M195 126l25-12" stroke="#8d6c43" stroke-width="3"/></g><path d="M151 33l8 9 18-20" fill="none" stroke="#efd7a8" stroke-width="4"/></svg>';
  if (kind === 'economy') return '<svg viewBox="0 0 360 180" aria-hidden="true">' + base.replace('#27364b', '#443b24') + '<g transform="translate(42 26)"><path d="M0 0v120h275" fill="none" stroke="#8e805d" stroke-width="2"/><path d="M0 30h275M0 60h275M0 90h275" stroke="#586052" opacity=".45"/><path d="M12 23l45 21 42-7 38 29 38 8 42 35 45 14" fill="none" stroke="#e28a67" stroke-width="4"/><path d="M211 119l11 4 8-10" fill="none" stroke="#e28a67" stroke-width="4"/><g fill="#d6b967"><rect x="20" y="77" width="35" height="43"/><rect x="63" y="91" width="35" height="29"/><rect x="106" y="100" width="35" height="20"/></g></g><g transform="translate(276 24)" fill="#d6b967"><ellipse cx="22" cy="10" rx="22" ry="8"/><path d="M0 10v50c0 12 44 12 44 0V10c0 12-44 12-44 0z" fill="#a88538"/><ellipse cx="22" cy="10" rx="22" ry="8" fill="#e4c878"/><path d="M22 2v16M15 6c11-8 20 3 7 7" fill="none" stroke="#6b5325" stroke-width="2"/></g></svg>';
  return '<svg viewBox="0 0 360 180" aria-hidden="true">' + base.replace('#27364b', '#2e414a') + '<g fill="#617380" stroke="#9aabb4"><path d="M62 83c-17-34 35-51 48-25 19-31 70-8 58 24 31-10 48 30 20 42H53c-29-8-22-36 9-41z"/></g><path d="M120 88l-22 43h24l-11 36 42-55h-25l16-24z" fill="#efd175"/><g stroke="#84aec4" stroke-width="3"><path d="M65 132l-8 19M178 132l-8 19M205 127l-8 19"/></g><path d="M0 158c42-20 74 17 116 0s78 18 122 0 76 16 122-1v23H0z" fill="#365f76"/><g transform="translate(269 28)"><path d="M0 39L21 0l21 39z" fill="#d99c58" stroke="#ffe0a1"/><path d="M21 12v13" stroke="#1a202b" stroke-width="3"/><circle cx="21" cy="32" r="2" fill="#1a202b"/></g></svg>';
}

/**
 * 插画区：底层永远是 SVG，上层叠写真图。
 * 图片 404 时 onerror 移除 <img>，自然露出下层 SVG，不留空框。
 */
function art(event) {
  const kind = EVENT_KINDS[event.kind] ? event.kind : 'disaster';
  const fallback = svgArt(kind);
  const src = artSource(event);
  if (!src) return fallback;
  return fallback + '<img class="ec-art-img" src="' + escapeHTML(src) + '" alt="" decoding="async" onerror="this.remove()">';
}

function deltaChip(number, label) {
  return '<span class="ec-delta ' + (number > 0 ? 'up' : 'down') + '">' + (number > 0 ? '+' : '') + escapeHTML(number) + ' <small>' + escapeHTML(label) + '</small></span>';
}

function effectSide(label, values) {
  const deltas = [];
  Object.keys(INDEX_LABELS).forEach(key => {
    const number = Number(values && values[key + '_delta']);
    if (!Number.isFinite(number) || number === 0) return;
    deltas.push(deltaChip(number, INDEX_LABELS[key]));
  });
  if (!deltas.length) return '';
  return '<div class="ec-effect-side"><span class="ec-side-name">' + escapeHTML(label) + '</span><div class="ec-deltas">' + deltas.join('') + '</div></div>';
}

/** 按受影响方结算的一行：label/role/count 只负责展示，deltas 用 interest/image/trust 原键名。 */
export function impactRow(imp) {
  if (!imp) return '';
  const deltas = [];
  const values = imp.deltas || {};
  Object.keys(INDEX_LABELS).forEach(key => {
    const number = Number(values[key]);
    if (!Number.isFinite(number) || number === 0) return;
    deltas.push(deltaChip(number, INDEX_LABELS[key]));
  });
  if (!deltas.length) return '';
  const count = Number(imp.count) || 0;
  const sub = count > 1 ? (count + ' 方') : (imp.role || '');
  return '<div class="ec-effect-side"><span class="ec-side-name">' + escapeHTML(imp.label || '各方') + (sub ? '<small>' + escapeHTML(sub) + '</small>' : '') + '</span><div class="ec-deltas">' + deltas.join('') + '</div></div>';
}

/** 事件对象 → 完整卡片 HTML（含 .ec-stage 舞台层）。 */
export function EventCardHTML(event) {
  const kind = EVENT_KINDS[event.kind] ? event.kind : 'disaster';
  const effects = event.effects || {};
  const hasImpacts = Array.isArray(event.impacts);
  const noEffect = Boolean(event.noEffect);
  let effectHtml = hasImpacts
    ? event.impacts.map(impactRow).join('')
    : effectSide(event.playerLabel || '我方', effects.player) + effectSide(event.agentLabel || '对方', effects.agent);
  if (noEffect) effectHtml = '<div class="ec-no-impact"><b>NO INDEX CHANGE</b><span>会场花絮，不改变任何代表团指数</span></div>';
  const serial = String(event.id || 'EVENT').toUpperCase();
  return '<div class="ec-stage"><article class="ec-card" role="dialog" aria-modal="true" aria-labelledby="ecEventTitle"><header class="ec-top"><span class="ec-suit">' + icon() + '</span><div class="ec-top-text"><div class="ec-eyebrow">NEGOTIATION EVENT</div><div class="ec-top-title">突发事件卡</div></div><span class="ec-serial">' + escapeHTML(serial) + '</span><button class="ec-close" type="button" data-ec-close aria-label="关闭事件卡"><svg viewBox="0 0 24 24"><path d="M5 5l14 14M19 5L5 19"/></svg></button></header><div class="ec-art">' + art(event) + '<span class="ec-art-label">' + escapeHTML(EVENT_KINDS[kind]) + '</span></div><div class="ec-body"><div class="ec-round">ROUND ' + escapeHTML(event.round || '—') + ' · ' + (noEffect ? '花絮' : '突发') + '</div><h2 class="ec-title" id="ecEventTitle">' + escapeHTML(event.title || '突发事件') + '</h2><p class="ec-text">' + escapeHTML(event.text || event.description || '会场出现新的变化，各方需要重新评估局势。') + '</p><p class="ec-flavor">' + escapeHTML(event.flavor || '会场风向正在改变，接下来的每一次表态都可能付出新的代价。') + '</p>' + ((noEffect || effectHtml) ? '<section class="ec-effects"><div class="ec-effects-title"><span>局势影响</span><span>INDEX CHANGE</span></div>' + (hasImpacts && !noEffect ? '<div class="ec-effects-note">只结算受影响方，未列入的代表团本轮指数不变</div>' : '') + effectHtml + '</section>' : '') + '</div><footer class="ec-bottom"><span class="ec-hint">EVENT CARD<br>KEEP THE TURN MOVING</span><button class="ec-continue" type="button" data-ec-close>继续谈判<svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6"/></svg></button></footer></article></div>';
}
