// Mermaid loader for China network access
// This script replaces Mermaid CDN with a China-accessible CDN
(function () {
  "use strict";

  function ensureMermaidInitialized() {
    if (typeof window.mermaid !== "undefined" && !window.mermaidInitialized) {
      window.mermaid.initialize({
        startOnLoad: true,
        theme: "default",
      });
      window.mermaidInitialized = true;
    }
  }

  function replaceMermaidScript() {
    const scripts = document.querySelectorAll("script[src*=\"mermaid\"]");

    const chinaCDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
    const fallbackCDN = "https://unpkg.com/mermaid@11/dist/mermaid.min.js";

    scripts.forEach(function (script) {
      const src = script.getAttribute("src") || "";

      if (src.includes("jsdelivr") || src.includes("unpkg")) {
        script.addEventListener("load", ensureMermaidInitialized, { once: true });
        return;
      }

      const newScript = document.createElement("script");
      newScript.src = chinaCDN;
      newScript.defer = true;

      newScript.onload = function () {
        ensureMermaidInitialized();
      };

      newScript.onerror = function () {
        const fallbackScript = document.createElement("script");
        fallbackScript.src = fallbackCDN;
        fallbackScript.defer = true;
        fallbackScript.onload = function () {
          ensureMermaidInitialized();
        };
        document.head.appendChild(fallbackScript);
      };

      script.parentNode.replaceChild(newScript, script);
    });

    if (scripts.length === 0 && typeof window.mermaid === "undefined") {
      const script = document.createElement("script");
      script.src = chinaCDN;
      script.defer = true;

      script.onload = function () {
        ensureMermaidInitialized();
      };

      script.onerror = function () {
        const fallbackScript = document.createElement("script");
        fallbackScript.src = fallbackCDN;
        fallbackScript.defer = true;

        fallbackScript.onload = function () {
          ensureMermaidInitialized();
        };

        document.head.appendChild(fallbackScript);
      };

      document.head.appendChild(script);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", replaceMermaidScript);
  } else {
    replaceMermaidScript();
  }

  setTimeout(replaceMermaidScript, 200);
})();
