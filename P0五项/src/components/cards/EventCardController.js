/**
 * 突发事件卡 · 控制器
 * 负责把 EventCardView 渲染的卡片挂载为全屏浮层：显示/关闭/排队/焦点管理。
 * 与旧版 window.NegotiationEventCard（IIFE 全局）等价，但收敛为 ES Module 实例。
 * 用法：const card = new EventCardController(); card.show(event); card.close();
 */
import { EventCardHTML } from './EventCardView.js';

export class EventCardController {
  constructor() {
    this.overlay = null;
    this.pending = [];
    this.active = false;
    this.lastFocus = null;
  }

  ensure() {
    if (this.overlay) return this.overlay;
    this.overlay = document.createElement('div');
    this.overlay.className = 'ec-overlay';
    this.overlay.setAttribute('aria-hidden', 'true');
    document.body.appendChild(this.overlay);
    this.overlay.addEventListener('click', event => {
      if (event.target === this.overlay) { this.close(); return; }
      if (event.target.closest && event.target.closest('[data-ec-close]')) this.close();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && this.active) this.close();
    });
    return this.overlay;
  }

  /** 显示一张事件卡；已有卡片在展示时进入队列，关闭后依次弹出。 */
  show(event) {
    if (!event) return;
    if (this.active) { this.pending.push(event); return; }
    this.active = true;
    this.lastFocus = document.activeElement;
    const overlay = this.ensure();
    overlay.innerHTML = EventCardHTML(event);
    overlay.setAttribute('aria-hidden', 'false');
    overlay.classList.remove('closing');
    requestAnimationFrame(() => {
      overlay.classList.add('open');
      overlay.querySelector('.ec-continue')?.focus();
    });
  }

  close() {
    if (!this.active || !this.overlay) return;
    const overlay = this.overlay;
    overlay.classList.add('closing');
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    setTimeout(() => {
      overlay.classList.remove('closing');
      this.active = false;
      if (this.lastFocus && this.lastFocus.focus) this.lastFocus.focus();
      if (this.pending.length) this.show(this.pending.shift());
    }, 240);
  }

  isOpen() { return this.active; }

  /** 批量入队。 */
  queue(events) { (events || []).forEach(event => this.show(event)); }
}
