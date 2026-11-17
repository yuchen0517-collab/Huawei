import { escapeHTML, icon } from './ui.js';

export function Modal() {
  return `<div class="modal-overlay" id="modalOverlay" aria-hidden="true"><section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modalTitle"><header class="modal-header"><div><h2 id="modalTitle">谈判战报</h2></div><button class="icon-button" data-action="close-modal" aria-label="关闭弹窗">${icon('close')}</button></header><div class="modal-content" id="modalContent"></div><footer class="modal-actions" id="modalActions"></footer></section></div>`;
}

export class ModalController {
  constructor(root) {
    this.root = root;
    this.title = root.querySelector('#modalTitle');
    this.content = root.querySelector('#modalContent');
    this.actions = root.querySelector('#modalActions');
    this.lastFocused = null;
  }

  open({ title, kicker = '', content, note = '', primary = '返回会场', secondary = null, onPrimary = null, onSecondary = null, primaryAction = '' }) {
    this.lastFocused = document.activeElement;
    this.title.textContent = title;
    const heading = this.title.parentElement;
    let kickerNode = heading.querySelector('#modalKicker');
    if (kicker) {
      if (!kickerNode) {
        kickerNode = document.createElement('span');
        kickerNode.id = 'modalKicker';
        heading.insertBefore(kickerNode, this.title);
      }
      kickerNode.textContent = kicker;
    } else if (kickerNode) {
      kickerNode.remove();
    }
    heading.classList.toggle('no-kicker', !kicker);
    this.content.innerHTML = content;
    this.actions.innerHTML = note ? `<span class="modal-note">${note}</span>` : '';
    if (secondary) this.actions.append(this.#action(secondary, 'secondary-button', onSecondary));
    this.actions.append(this.#action(primary, 'solid-button', onPrimary, primaryAction));
    this.root.classList.add('open');
    this.root.setAttribute('aria-hidden', 'false');
    this.root.querySelector('[data-action="close-modal"]').focus();
  }

  #action(label, className, handler, actionName = '') {
    const button = document.createElement('button');
    button.className = className;
    button.textContent = label;
    if (actionName) button.dataset.action = actionName;
    button.addEventListener('click', () => handler ? handler() : this.close());
    return button;
  }

  close() {
    this.root.classList.remove('open');
    this.root.setAttribute('aria-hidden', 'true');
    if (this.lastFocused) this.lastFocused.focus();
  }

  handleKeyboard(event) {
    if (!this.root.classList.contains('open')) return;
    if (event.key === 'Escape') return this.close();
    if (event.key !== 'Tab') return;
    const focusable = [...this.root.querySelectorAll('button, [href], select, input, textarea, summary, [tabindex]:not([tabindex="-1"])')].filter(element => !element.disabled);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
}

export function SafeText({ text }) {
  return `<p>${escapeHTML(text)}</p>`;
}