import { icon, escapeHTML } from './ui.js';

/**
 * 通栏议题条：纯色底，横向铺满视口，压在背景图之上，与背景不产生渐变衔接。
 * 标题在页面中心绝对定位，右侧只放突发事件 / 谈判树两个入口。
 */
export function Topicbar({ topic, unreadEvents = 0 }) {
  return `<div class="topicbar">
    <strong class="topicbar-title">${escapeHTML(topic.title)}</strong>
    <div class="topicbar-actions">
      <button class="topic-button event-button" data-action="show-event" aria-label="突发事件" title="突发事件">${icon('bolt')}<span class="topic-button-label">突发事件</span><span id="eventCount" class="event-count">${unreadEvents}</span></button>
      <button class="topic-button" data-action="show-tree" aria-label="谈判树" title="谈判树">${icon('tree')}<span class="topic-button-label">谈判树</span></button>
    </div>
  </div>`;
}
