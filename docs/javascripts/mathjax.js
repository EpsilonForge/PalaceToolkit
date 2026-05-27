window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: "tex2jax_ignore|mathjax_ignore",
    processHtmlClass: "arithmatex|jp-RenderedHTMLCommon|jp-RenderedMarkdown",
  },
};

(() => {
  const mathTargetSelector = [
    ".arithmatex",
    ".jp-RenderedMarkdown",
    ".jp-RenderedHTMLCommon",
  ].join(", ");

  const typesetMath = () => {
    if (!window.MathJax || typeof window.MathJax.typesetPromise !== "function") {
      return;
    }

    const targets = Array.from(document.querySelectorAll(mathTargetSelector));
    const nodes = targets.length > 0 ? targets : [document.body];

    window.MathJax.typesetPromise(nodes).catch((error) => {
      console.error("MathJax typeset failed:", error);
    });
  };

  // Run once after all scripts are loaded.
  window.addEventListener("load", typesetMath);

  // Re-typeset after Material for MkDocs instant navigation updates the DOM.
  const subscribeToInstantNavigation = () => {
    if (typeof document$ !== "undefined" && document$.subscribe) {
      document$.subscribe(() => {
        window.requestAnimationFrame(typesetMath);
      });
    }
  };

  if (document.readyState === "complete") {
    subscribeToInstantNavigation();
  } else {
    window.addEventListener("load", subscribeToInstantNavigation);
  }
})();
