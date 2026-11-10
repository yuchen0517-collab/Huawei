/* ============================================================
   外交谈判模拟器 · 全站主题控制器（webdemo 1.6）
   - 自动：按本机时间 7:00–19:00 亮色，其余深色
   - 手动：单击主题按钮切换，长按 / Shift+单击 恢复自动
   - 所有页面共用 localStorage：neg-theme-mode / neg-theme
   页面需在 <head> 里放主题引导脚本（首屏防闪），并在
   <body> 末尾引入本文件；按钮统一为 .theme-toggle。
   ============================================================ */
(function () {
  'use strict';
  if (window.__negThemeInstalled) return;
  window.__negThemeInstalled = true;

  var CFG        = window.THEME_CFG || { dayStart: 7, dayEnd: 19 };
  var MODE_KEY   = 'neg-theme-mode';
  var THEME_KEY  = 'neg-theme';
  var META_COLOR = { dark: '#070402', light: '#f9f2e3' };
  var CHECK_MS   = 30000;
  var LONG_PRESS = 600;

  var html  = document.documentElement;
  var meta  = document.querySelector('meta[name="theme-color"]');
  var btns  = Array.prototype.slice.call(document.querySelectorAll('.theme-toggle'));
  var mode  = 'auto';
  var ticker = null, toastTimer = null, pressTimer = null, swallowClick = false;
  var fallbackToast = null;

  function read(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function write(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }

  function isDaytime(date) {
    var mins = date.getHours() * 60 + date.getMinutes();
    return mins >= CFG.dayStart * 60 && mins < CFG.dayEnd * 60;
  }
  function themeForTime(date) { return isDaytime(date || new Date()) ? 'light' : 'dark'; }
  function currentTheme() { return html.getAttribute('data-theme') === 'light' ? 'light' : 'dark'; }
  function themeName(theme) { return theme === 'light' ? '白天 · 亮色' : '夜间 · 深色'; }

  function paint(theme) {
    html.setAttribute('data-theme', theme);
    if (meta) meta.setAttribute('content', META_COLOR[theme] || META_COLOR.dark);
    var auto = mode === 'auto';
    btns.forEach(function (btn) {
      btn.classList.toggle('is-auto', auto);
      btn.title = auto
        ? '主题：跟随系统时间（当前 ' + themeName(theme) + '）\n单击可手动切换，长按或 Shift+单击恢复自动'
        : '主题：手动（当前 ' + themeName(theme) + '）\n单击切换，长按或 Shift+单击恢复跟随时间';
      btn.setAttribute('aria-label', auto ? '主题跟随系统时间，单击手动切换，长按恢复自动' : '切换亮暗主题');
      btn.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
    });
  }

  function toastEl() {
    var t = document.getElementById('themeToast');
    if (t) return t;
    /* 只用主题自己的提示条，避免和页面的 #toast 抢文案 */
    if (!fallbackToast) {
      fallbackToast = document.createElement('div');
      fallbackToast.setAttribute('role', 'status');
      fallbackToast.setAttribute('aria-live', 'polite');
      fallbackToast.style.cssText =
        'position:fixed;left:50%;bottom:28px;transform:translate(-50%,10px);z-index:9999;' +
        'padding:10px 18px;border-radius:22px;border:1px solid rgba(201,160,97,.45);' +
        'background:rgba(18,10,5,.92);color:#efd7a8;font-size:12px;letter-spacing:.06em;' +
        'opacity:0;pointer-events:none;transition:opacity .3s ease,transform .3s ease;' +
        'backdrop-filter:blur(8px);max-width:86vw;text-align:center;';
      document.body.appendChild(fallbackToast);
    }
    return fallbackToast;
  }
  function say(message) {
    var t = toastEl();
    if (!t) return;
    var textEl = t.querySelector('#themeToastText');
    if (textEl) textEl.textContent = message;
    else t.textContent = message;
    if (t.id === 'toast' && !t.classList.contains('toast')) {
      // 兼容不带动画类的容器
    }
    t.classList.add('show');
    if (!t.classList.contains('toast') && t === fallbackToast) {
      t.style.opacity = '1';
      t.style.transform = 'translate(-50%,0)';
    }
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      t.classList.remove('show');
      if (t === fallbackToast) {
        t.style.opacity = '0';
        t.style.transform = 'translate(-50%,10px)';
      }
    }, 2800);
  }

  function syncAuto(persist) {
    if (mode !== 'auto') return;
    var theme = themeForTime();
    if (persist) write(THEME_KEY, theme);
    paint(theme);
  }
  function stopTicker() { if (ticker) { clearInterval(ticker); ticker = null; } }
  function startTicker() {
    stopTicker();
    ticker = setInterval(function () { if (mode === 'auto') syncAuto(false); }, CHECK_MS);
  }
  function useAuto(announce) {
    mode = 'auto';
    write(MODE_KEY, 'auto');
    syncAuto(true);
    startTicker();
    if (announce) say('已恢复跟随系统时间自动切换（' + themeName(currentTheme()) + '）');
  }
  function useManual(theme) {
    mode = 'manual';
    write(MODE_KEY, 'manual');
    write(THEME_KEY, theme);
    stopTicker();
    paint(theme);
  }

  function toggle(event) {
    if (event && event.shiftKey) { useAuto(true); return; }
    if (swallowClick) { swallowClick = false; return; }
    var next = currentTheme() === 'light' ? 'dark' : 'light';
    var fromAuto = mode === 'auto';
    useManual(next);
    if (fromAuto) say('已切换为手动模式（' + themeName(next) + '），长按按钮可恢复跟随时间');
  }
  window.toggleTheme = toggle;

  function onPressStart(e) {
    if (e && e.button !== undefined && e.button !== 0) return;
    swallowClick = false;
    clearTimeout(pressTimer);
    pressTimer = setTimeout(function () {
      swallowClick = true;
      useAuto(true);
      setTimeout(function () { swallowClick = false; }, 4000);
    }, LONG_PRESS);
  }
  function onPressEnd() { clearTimeout(pressTimer); }
  window.addEventListener('pointerup', onPressEnd);
  window.addEventListener('pointercancel', onPressEnd);

  btns.forEach(function (btn) {
    btn.addEventListener('pointerdown', onPressStart);
    btn.addEventListener('pointerup', onPressEnd);
    btn.addEventListener('pointercancel', onPressEnd);
    btn.addEventListener('pointerleave', onPressEnd);
    btn.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  });

  function restore() {
    if (read(MODE_KEY) === 'manual') {
      useManual(read(THEME_KEY) === 'light' ? 'light' : 'dark');
    } else {
      useAuto(false);
    }
  }

  restore();

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') syncAuto(false);
  });
  window.addEventListener('focus', function () { syncAuto(false); });
  window.addEventListener('pageshow', function () { restore(); });
  window.addEventListener('storage', function (e) {
    if (e.key !== MODE_KEY && e.key !== THEME_KEY) return;
    restore();
  });

  window.ThemeControl = {
    auto: function () { useAuto(true); },
    manual: function (theme) {
      useManual(theme === 'light' || theme === 'dark' ? theme : currentTheme());
    },
    getMode: function () { return mode; },
    getTheme: currentTheme
  };
})();
