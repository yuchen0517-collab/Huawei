export function Toast() {
  return '<div class="toast" id="toast" role="status"><span></span></div>';
}

export class ToastController {
  constructor(root, duration = 2600) {
    this.root = root;
    this.duration = duration;
    this.timer = null;
  }

  show(message) {
    this.root.querySelector('span').textContent = message;
    this.root.classList.add('show');
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.root.classList.remove('show'), this.duration);
  }
}
