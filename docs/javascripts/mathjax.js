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

  if (document.readyState === "complete" || document.readyState === "interactive") {
    window.requestAnimationFrame(typesetMath);
  } else {
    window.addEventListener("DOMContentLoaded", () => {
      window.requestAnimationFrame(typesetMath);
    });
  }

  // Some browsers restore page state from bfcache on history navigation.
  window.addEventListener("pageshow", () => {
    window.requestAnimationFrame(typesetMath);
  });
})();
