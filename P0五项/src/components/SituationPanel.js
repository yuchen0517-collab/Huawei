import { Avatar, FoldSection, icon, Metric, PanelHeading } from './ui.js';

const REL_PARTIES = [
  { id: 'cn', label: '中' },
  { id: 'us', label: '美' }
];

const REL_DIMS = [
  { id: 'affinity', label: '亲和' },
  { id: 'hostility', label: '敌意' },
  { id: 'trust', label: '信任' }
];

const REL_DATA = {
  affinity: [
    [null, 42],
    [38, null]
  ],
  hostility: [
    [null, 47],
    [55, null]
  ],
  trust: [
    [null, 31],
    [27, null]
  ]
};

function level(value) {
  if (value == null) return 'diagonal';
  if (value >= 65) return 'lv3';
  if (value >= 35) return 'lv2';
  return 'lv1';
}

export function RelationMatrix({ dim = 'affinity' }) {
  const data = REL_DATA[dim] || REL_DATA.affinity;
  const heads = REL_PARTIES.map(party => `<div class="rel-head">${party.label}</div>`).join('');
  const rows = data.map((row, rowIndex) => {
    const cells = row.map((value, colIndex) => value == null
      ? `<div class="rel-cell rel-diagonal" aria-label="${REL_PARTIES[rowIndex].label}对${REL_PARTIES[colIndex].label} 无数据">—</div>`
      : `<div class="rel-cell dim-${dim} ${level(value)}" aria-label="${REL_PARTIES[rowIndex].label}对${REL_PARTIES[colIndex].label} ${value}"><span class="rel-value">${value}</span><span class="rel-bar" aria-hidden="true"><i style="width:${value}%"></i></span></div>`).join('');
    return `<div class="rel-row-label">${REL_PARTIES[rowIndex].label}</div>${cells}`;
  }).join('');
  const pills = REL_DIMS.map(item => `<button class="rel-pill${item.id === dim ? ' active' : ''}" data-action="matrix-dim" data-dim="${item.id}" aria-pressed="${item.id === dim}">${item.label}</button>`).join('');

  return `<div class="rel-matrix">
    <div class="rel-dims" role="group" aria-label="关系矩阵维度">${pills}</div>
    <div class="rel-grid"><div class="rel-corner" aria-hidden="true"></div>${heads}${rows}</div>

  </div>`;
}

export function MetricList({ metrics }) {
  const definitions = [
    { id: 'interest', label: '主体利益', delta: '+4', previous: 58 },
    { id: 'image', label: '国际形象', delta: '+2', tone: 'blue', previous: 72 },
    { id: 'trust', label: '盟友信任', delta: '−2', tone: 'purple', previous: 60, negative: true }
  ];
  return definitions.map(definition => Metric({ ...definition, value: metrics[definition.id] })).join('');
}

function OpponentSituation() {
  return `<div class="opponent-situation"><div class="situation-head">${Avatar({ party: { id: 'us', name: '美国代表团' }, mini: true })}<strong>美国代表团</strong><em>有限合作窗口</em></div><div class="situation-grid"><div><span>公开形象</span><strong>60 <i>+2</i></strong></div><div><span>对我信任</span><strong>较低 → 缓和</strong></div><div><span>核心利益</span><strong>有限满足</strong></div><div><span>合作窗口</span><strong>有限开放</strong></div></div></div>`;
}

function ChannelPreview() {
  return `<div class="channel-preview locked" aria-disabled="true">${icon('lock')}<span><strong>非正式沟通</strong><small>本场景不开放 · 无法进入非正式沟通</small></span>${icon('lock')}</div>`;
}

function TaskList() {
  return `<div class="task-list"><p><i></i>确立公共算力配额原则</p><p><i></i>限制安全审查适用范围</p><p><i></i>争取两个以上中间阵营支持</p></div>`;
}

export function SituationPanel({ metrics, dim = 'affinity' }) {
  return `<aside class="side-panel situation-panel" id="situationPanel" aria-label="态势分析" tabindex="-1">
    ${PanelHeading({ title: '态势', collapseAction: 'collapse-situation', collapseLabel: '收起态势分析', direction: 'chevron' })}
    ${FoldSection({ title: '三项指数', open: true, content: `<div class="metric-list" id="metricList">${MetricList({ metrics })}</div>` })}
    ${FoldSection({ title: '对方态势', open: true, content: OpponentSituation() })}
    ${FoldSection({ title: '外交渠道', open: true, content: ChannelPreview() })}
    ${FoldSection({ title: '谈判任务', badge: '0 / 3', content: TaskList() })}
    ${FoldSection({ title: '关系矩阵', content: `<div id="relationMatrix">${RelationMatrix({ dim })}</div>` })}
  </aside><button class="reopen-rail reopen-right" data-action="reopen-situation" aria-label="展开态势分析" aria-expanded="false">${icon('back')}<span>态势</span></button>`;
}