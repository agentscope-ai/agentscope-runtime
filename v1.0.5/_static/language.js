(function () {
  "use strict";

  function getCurrentPageLanguage() {
    const path = window.location.pathname;
    if (path.includes("/zh/")) {
      return "zh";
    }
    return "en";
  }

  function autoSetLanguage() {
    const currentLang = getCurrentPageLanguage();
    const savedLang = localStorage.getItem("preferred-language");

    if (currentLang !== savedLang) {
      localStorage.setItem("preferred-language", currentLang);
    }

    setTimeout(() => {
      if (window.switchLanguage) {
        window.switchLanguage(currentLang, true);
      }
    }, 5);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoSetLanguage);
  } else {
    autoSetLanguage();
  }
})();