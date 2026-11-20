import { icon, formatRound } from './ui.js';

export function Topbar({ round, maxRounds, version = 1 }) {
  return `<header class="topbar">
    <div class="brand-zone">
      <button class="icon-button back-button" data-action="back" aria-label="返回谈判大厅" title="返回谈判大厅">${icon('back')}</button>
      <div class="brand-copy"><strong>DIPLOMAT</strong><span>外交谈判模拟器</span></div>
    </div>
    <div class="round-status" aria-label="谈判轮次"><span>ROUND</span><strong id="roundNumber">${formatRound(round)}</strong><small>/ ${maxRounds}</small><em class="version-chip" id="mVer" title="协议版本号">v${version}</em></div>
    <div class="top-actions">
      <button class="icon-button theme-button" data-action="toggle-theme" aria-label="切换明暗主题" title="切换明暗主题">${icon('moon', 'moon')}${icon('sun', 'sun')}</button>
      <button class="outline-button" data-action="restart">重新谈判</button>
      <button class="outline-button end-button" data-action="end-negotiation">结束谈判</button>
    </div>
  </header>`;
}
