import { Avatar, FoldSection, icon, Metric, PanelHeading } from './ui.js';
import { parties } from '../domain/negotiation.js';

export function MetricList({ metrics }) {
  const definitions = [
    { id: 'interest', label: '主体利益', delta: '+4', previous: 58 },
    { id: 'image', label: '国际形象', delta: '+2', tone: 'blue', previous: 72 },
    { id: 'trust', label: '盟友信任', delta: '−2', tone: 'purple', previous: 60, negative: true }
  ];
  return definitions.map(definition => Metric({ ...definition, value: metrics[definition.id] })).join('');
}

function OpponentSituation() {
  return `<button class="opponent-situation" data-action="show-opponent"><div class="situation-head">${Avatar({ party: parties.us, mini: true })}<strong>美国代表团</strong><em>有限合作窗口</em></div><div class="situation-grid"><div><span>公开形象</span><strong>60 <i>+2</i></strong><small>公开评价</small></div><div><span>对我信任</span><strong>较低 → 缓和</strong><small>估计 · 可信度中</small></div><div><span>核心利益</span><strong>有限满足</strong><small>情报区间 45～55</small></div><div><span>合作窗口</span><strong>有限开放</strong><small>2 条公开依据</small></div></div><span class="evidence-link">查看研判依据 →</span></button>`;
}

function ChannelPreview() {
  return `<button class="channel-preview" data-action="show-channel">${icon('lock')}<span><strong>非正式沟通</strong><small>可私下探底 · 暂不开放秘密附件</small></span>${icon('chevron')}</button>`;
}

function TaskList() {
  return `<div class="task-list"><p><i></i>确立公共算力配额原则</p><p><i></i>限制安全审查适用范围</p><p><i></i>争取两个以上中间阵营支持</p></div>`;
}

function RelationMatrix() {
  return `<div class="matrix-mini"><div><span></span><b>中</b><b>美</b><b>欧</b></div><div><strong>中</strong><i>—</i><i class="warm">42</i><i>68</i></div><div><strong>美</strong><i class="warm">38</i><i>—</i><i>71</i></div><div><strong>欧</strong><i>65</i><i>69</i><i>—</i></div></div>`;
}

export function SituationPanel({ metrics }) {
  return `<aside class="side-panel situation-panel" id="situationPanel" aria-label="态势分析">
    ${PanelHeading({ kicker: 'SITUATION ROOM', title: '态势', collapseAction: 'collapse-situation', collapseLabel: '收起态势分析', direction: 'chevron' })}
    ${FoldSection({ title: '三项指数', open: true, content: `<div class="metric-list" id="metricList">${MetricList({ metrics })}</div>` })}
    ${FoldSection({ title: '对方态势', open: true, content: OpponentSituation() })}
    ${FoldSection({ title: '外交渠道', badge: '本场景授权', open: true, content: ChannelPreview() })}
    ${FoldSection({ title: '谈判任务', badge: '0 / 3', content: TaskList() })}
    ${FoldSection({ title: '关系矩阵', content: RelationMatrix() })}
  </aside><button class="reopen-rail reopen-right" data-action="reopen-situation" aria-label="展开态势分析">${icon('back')}<span>态势</span></button>`;
}
