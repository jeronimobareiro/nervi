// SPDX-License-Identifier: GPL-3.0-or-later
// Selector de idioma: al cambiar de idioma, queda en la misma página (si existe en el otro idioma).
// Cada idioma es un sitio completo: español en la raíz y /en/, /pt/, /ru/ debajo.
document.addEventListener("DOMContentLoaded", function () {
  var enlaces = Array.prototype.slice.call(document.querySelectorAll(".md-select__link[hreflang]"));
  if (!enlaces.length) return;
  var raices = enlaces.map(function (a) {
    var r = new URL(a.href, location.href).pathname;
    return r.endsWith("/") ? r : r + "/";
  });
  // La raíz más larga que contiene la página actual es la del idioma actual.
  var actual = "";
  raices.forEach(function (r) {
    if (location.pathname.indexOf(r) === 0 && r.length > actual.length) actual = r;
  });
  if (!actual) return;
  var resto = location.pathname.slice(actual.length) + location.search + location.hash;
  enlaces.forEach(function (a, i) {
    a.href = raices[i] + resto;
  });
});
