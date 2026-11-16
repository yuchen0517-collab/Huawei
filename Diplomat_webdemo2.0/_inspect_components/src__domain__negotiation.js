export const topic = {
  id: 'global-ai-governance',
  eyebrow: 'GLOBAL AI GOVERNANCE',
  title: '全球 AI 治理框架公约',
  mode: '双边谈判',
  maxRounds: 15
};

export const strategyCatalog = [
  { id: 'clarify', cost: 1, type: 'TACTICAL · 试探', name: '澄清核查边界', description: '要求对方定义审查范围与期限', effect: '情报可信度 +1 级' },
  { id: 'bundle', cost: 1, type: 'TACTICAL · 交换', name: '议题捆绑', description: '以许可豁免交换公共算力配额', effect: '主体利益 +3～5', recommended: true },
  { id: 'package', cost: 2, type: 'STRATEGIC · 破局', name: '提出一揽子方案', description: '配额、许可与核查同步打包', effect: '主体利益 +4～7' },
  { id: 'initiative', cost: 1, type: 'PUBLIC · 造势', name: '发起公开倡议', description: '争取中间阵营支持治理原则', effect: '国际形象 +2' },
  { id: 'concession', cost: 2, type: 'CONCESSION · 回旋', name: '审慎条件让步', description: '以有限承诺换取程序性保障', effect: '盟友信任 +1' }
];

export const parties = {
  us: { id: 'us', code: 'US', name: '美国代表团' },
  cn: { id: 'cn', code: 'CN', name: '中国代表团 · 我方', self: true }
};

export const initialSpeeches = [
  {
    id: 'opening-us', party: 'us', label: 'ROUND 01 · 开场陈述',
    html: '我们愿意讨论全球 AI 治理合作，但任何框架都必须包含<strong>可追溯的安全审查</strong>。在核心技术与数据跨境问题上，我们不会接受无条件开放。'
  },
  {
    id: 'opening-cn', party: 'cn', label: 'ROUND 01 · 立场回应',
    html: '合作应建立在平等与互惠之上。我方支持合理安全关切，但审查必须<strong>范围明确、期限有限、程序透明</strong>，不能成为技术壁垒的另一种形式。'
  },
  {
    id: 'opening-latest', party: 'us', label: '最新表态', badge: '态度松动',
    html: '程序透明可以谈。若贵方能在公共算力配额上给出更明确的安排，我们愿意重新评估<strong>逐案许可</strong>的适用范围。',
    advisor: '对方释放了有限合作窗口，建议用明确对价推进交换。'
  }
];

export function createInitialNegotiation() {
  return {
    round: 1,
    maxRounds: topic.maxRounds,
    actionPoints: 5,
    selectedIds: [],
    metrics: { interest: 62, image: 74, trust: 58 },
    log: [{ round: 1, text: '双方完成开场陈述，美方释放有限合作窗口。' }],
    ended: false,
    eventRead: false
  };
}
