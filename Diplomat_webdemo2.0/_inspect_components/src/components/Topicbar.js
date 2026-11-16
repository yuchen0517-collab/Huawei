import { escapeHTML, icon } from './ui.js';

export function Topicbar({ topic, unreadEvents }) {
  return `<section class="topicbar" aria-label="当前议题">
    <div class="topic-title"><span class="live-dot"></span><div><span>${escapeHTML(topic.eyebrow)}</span><strong><span class="topic-prefix">议题 · </span>${escapeHTML(topic.title)}</strong></div></div>
    <div class="topic-actions">
      <button class="topic-button event-button" data-action="show-event">${icon('bolt')}突发事件<span id="eventCount">${unreadEvents}</span></button>
      <button class="topic-button" data-action="show-tree">${icon('tree')}谈判树</button>
    </div>
  </section>`;
}
