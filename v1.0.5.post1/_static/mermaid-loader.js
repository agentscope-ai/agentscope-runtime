// Mermaid loader for China network access
// This script replaces Mermaid CDN with a China-accessible CDN
(function() {
  "use strict";

  // Function to replace Mermaid script source
  function replaceMermaidScript() {
    // Find all script tags that load Mermaid
    const scripts = document.querySelectorAll("script[src*=\"mermaid\"]");
    const chinaCDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
    const fallbackCDN = "https://unpkg.com/mermaid@10/dist/mermaid.min.js";

    scripts.forEach(function(script) {
      const src = script.getAttribute("src");
      // If script is from an inaccessible CDN, replace it
      if (src && !src.includes("jsdelivr") && !src.includes("unpkg")) {
        const newScript = document.createElement("script");
        newScript.src = chinaCDN;
        newScript.onload = function() {
          // Initialize Mermaid if not already initialized
          if (typeof mermaid !== "undefined" && !window.mermaidInitialized) {
            mermaid.initialize({
              startOnLoad: true,
              theme: "default"
            });
            window.mermaidInitialized = true;
            // Re-render any existing mermaid diagrams
            mermaid.run();
          }
        };
        newScript.onerror = function() {
          // Fallback to unpkg if jsdelivr fails
          const fallbackScript = document.createElement("script");
          fallbackScript.src = fallbackCDN;
          fallbackScript.onload = function() {
            if (typeof mermaid !== "undefined" && !window.mermaidInitialized) {
              mermaid.initialize({
                startOnLoad: true,
                theme: "default"
              });
              window.mermaidInitialized = true;
              mermaid.run();
            }
          };
          document.head.appendChild(fallbackScript);
        };
        script.parentNode.replaceChild(newScript, script);
      } else if (src && (src.includes("jsdelivr") || src.includes("unpkg"))) {
        // If already using a good CDN, just ensure initialization
        script.onload = function() {
          if (typeof mermaid !== "undefined" && !window.mermaidInitialized) {
            mermaid.initialize({
              startOnLoad: true,
              theme: "default"
            });
            window.mermaidInitialized = true;
          }
        };
      }
    });

    // If no Mermaid script found, load it ourselves
    if (scripts.length === 0 && typeof mermaid === "undefined") {
      const script = document.createElement("script");
      script.src = chinaCDN;
      script.onload = function() {
        if (typeof mermaid !== "undefined") {
          mermaid.initialize({
            startOnLoad: true,
            theme: "default"
          });
          window.mermaidInitialized = true;
        }
      };
      script.onerror = function() {
        const fallbackScript = document.createElement("script");
        fallbackScript.src = fallbackCDN;
        fallbackScript.onload = function() {
          if (typeof mermaid !== "undefined") {
            mermaid.initialize({
              startOnLoad: true,
              theme: "default"
            });
            window.mermaidInitialized = true;
          }
        };
        document.head.appendChild(fallbackScript);
      };
      document.head.appendChild(script);
    }
  }

  // Run when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", replaceMermaidScript);
  } else {
    replaceMermaidScript();
  }

  // Also run after a short delay to catch dynamically loaded scripts
  setTimeout(replaceMermaidScript, 100);
})();

