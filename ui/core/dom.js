(function (D) {
  "use strict";

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function setHtml(id, html) {
    var n = $(id);
    if (n) n.innerHTML = html;
  }

  function toggle(id, cls, on) {
    var n = $(id);
    if (n) n.classList.toggle(cls, !!on);
  }

  function on(root, type, selector, fn) {
    root.addEventListener(type, function (e) {
      var t = e.target.closest(selector);
      if (t && root.contains(t)) fn(t, e);
    });
  }

  D.dom = { $: $, el: el, esc: esc, setHtml: setHtml, toggle: toggle, on: on };
})(window.D = window.D || {});