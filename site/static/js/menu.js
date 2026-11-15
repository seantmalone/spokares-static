/*
 * The phone menu (under 1020px): the "Menu" button opens the links under the
 * bar and reads "Close" while they are open. As on the WordPress site:
 * opening moves focus to the first link and Tab stays inside the menu (the
 * button, the links, Join); Escape closes it and puts focus back on the
 * button; the page does not scroll while it is open; choosing a link, clicking
 * outside the menu or widening the window past 1020px closes it. From 1020px
 * up site.css shows the links in the bar and hides the button. Without
 * JavaScript site.css shows the links in a row under the bar instead; that
 * layout is keyed on <html> lacking the class "js", which this script adds, so
 * it is also used when this file fails to load.
 */
(function () {
  var nav = document.querySelector('.nav');
  if (!nav) return;
  document.documentElement.classList.add('js');
  var button = nav.querySelector('.nav__toggle');
  var list = nav.querySelector('.nav__list');
  var wide = window.matchMedia('(min-width: 1020px)');

  function links() {
    return Array.prototype.slice.call(list.querySelectorAll('a[href]'));
  }

  function isOpen() {
    return nav.classList.contains('is-open');
  }

  // Focus the button without scrolling the page (html has scroll-padding-top,
  // so a plain focus() jumps). Older browsers ignore preventScroll, so the
  // scroll position is put back by hand as well.
  function focusButton() {
    var x = window.pageXOffset, y = window.pageYOffset;
    try { button.focus({ preventScroll: true }); } catch (err) { button.focus(); }
    if (window.pageXOffset !== x || window.pageYOffset !== y) window.scrollTo(x, y);
  }

  function set(open) {
    nav.classList.toggle('is-open', open);
    document.documentElement.classList.toggle('nav-open', open);
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    button.textContent = open ? 'Close' : 'Menu';
  }

  button.addEventListener('click', function () {
    var open = !isOpen();
    set(open);
    if (open) links()[0].focus();
  });

  document.addEventListener('keydown', function (e) {
    if (!isOpen()) return;
    if (e.key === 'Escape') {
      set(false);
      focusButton();
      return;
    }
    if (e.key === 'Tab') {
      var all = links();
      var first = button;
      var last = all[all.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });

  nav.addEventListener('click', function (e) {
    if (e.target.closest('a')) set(false);
  });

  document.addEventListener('click', function (e) {
    if (isOpen() && !nav.contains(e.target)) set(false);
  });

  function onWidthChange() {
    var hadFocus = document.activeElement === button;
    var inList = list.contains(document.activeElement);
    set(false);
    // The button is hidden from 1020px up and the links are hidden below it;
    // keep focus on something visible.
    if (hadFocus && wide.matches) links()[0].focus();
    if (inList && !wide.matches) focusButton();
  }
  // Safari before 14 has only the older addListener.
  if (wide.addEventListener) wide.addEventListener('change', onWidthChange);
  else if (wide.addListener) wide.addListener(onWidthChange);
})();
