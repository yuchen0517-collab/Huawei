import { escapeHTML, formatRound, icon } from './ui.js';

export function TreeDrawerHeader({ topic, round, nodeCount, version = 1 }) {
  return `<header class="drawer-header"><div class="drawer-heading"><span>NEGOTIATION TREE</span><h2 id="treeDrawerTitle">谈判树</h2><p>${escapeHTML(topic.title)} · ${escapeHTML(topic.mode)}</p></div><div class="drawer-stats"><div><strong>第 ${formatRound(round)} 轮</strong><small>当前</small></div><div><strong>${nodeCount}</strong><small>节点</small></div><div><strong class="version-chip" id="drVer">v${version}</strong><small>协议版本</small></div></div><button class="icon-button" data-action="close-tree" aria-label="关闭谈判树">${icon('close')}</button></header>`;
}

/** 抽屉里只有谈判树；协议签署板已回到报价板弹窗。 */
export function TreeDrawer({ topic, round, nodeCount, version = 1 }) {
  return `<div class="drawer-backdrop" id="drawerBackdrop" data-action="close-tree"></div><aside class="tree-drawer" id="treeDrawer" role="dialog" aria-modal="true" aria-labelledby="treeDrawerTitle" aria-hidden="true">${TreeDrawerHeader({ topic, round, nodeCount, version })}<div class="drawer-body" id="treeDrawerBody"></div></aside>`;
}