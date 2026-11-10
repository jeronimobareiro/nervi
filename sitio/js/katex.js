// SPDX-License-Identifier: GPL-3.0-or-later
// Renderiza las fórmulas ($...$ y $$...$$) con KaTeX, también al navegar sin recargar.
document$.subscribe(() => {
  renderMathInElement(document.body, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false },
      { left: "\\(", right: "\\)", display: false },
      { left: "\\[", right: "\\]", display: true },
    ],
  });
});
