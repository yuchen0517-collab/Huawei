(function () {
  'use strict';

  var KEYS = ['neg-l1-state', 'neg-l2-state', 'neg-l3-state'];
  var CARDS = ['k1', 'k2', 'k3', 'k4'];

  function read(level) {
    try {
      var value = JSON.parse(localStorage.getItem(KEYS[level - 1]) || 'null');
      if (!value || typeof value !== 'object') return { mastered: [], drill: null };
      var mastered = Array.isArray(value.mastered) ? value.mastered.filter(function (key, index, all) {
        return CARDS.indexOf(key) !== -1 && all.indexOf(key) === index;
      }) : [];
      return { mastered: mastered, drill: value.drill === 'B' ? 'B' : null };
    } catch (e) {
      return { mastered: [], drill: null };
    }
  }

  function completed(level) {
    var state = read(level);
    return state.mastered.length + (state.drill === 'B' ? 1 : 0);
  }

  function percent(level) {
    return completed(level) * 20;
  }

  function isComplete(level) {
    return completed(level) === 5;
  }

  function isUnlocked(level) {
    for (var i = 1; i < level; i++) {
      if (!isComplete(i)) return false;
    }
    return true;
  }

  function totalPercent() {
    return Math.round((completed(1) + completed(2) + completed(3)) / 15 * 100);
  }

  function allComplete() {
    return isComplete(1) && isComplete(2) && isComplete(3);
  }

  function requireLevel(level) {
    if (isUnlocked(level)) return true;
    location.replace('index.html');
    return false;
  }

  window.LearningProgress = {
    read: read,
    completed: completed,
    percent: percent,
    isComplete: isComplete,
    isUnlocked: isUnlocked,
    totalPercent: totalPercent,
    allComplete: allComplete,
    requireLevel: requireLevel
  };
})();
