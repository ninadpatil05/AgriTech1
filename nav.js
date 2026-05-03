/**
 * Shared navigation for AgriTech — Smart Crop Detective
 * @param {string} activePage - dashboard | detect | library | weather | reports | about | contact | index
 */
export function renderNav(activePage) {
  const root = document.getElementById("nav-root");
  if (!root) return;

  const brand = "AgriTech — Smart Crop Detective";
  const items = [
    { id: "dashboard", href: "dashboard.html", label: "Home" },
    { id: "detect", href: "detect.html", label: "Detect Crop" },
    { id: "library", href: "library.html", label: "Disease Library" },
    { id: "weather", href: "weather.html", label: "Weather" },
    { id: "reports", href: "reports.html", label: "Reports" },
    { id: "about", href: "about.html", label: "About" },
    { id: "contact", href: "contact.html", label: "Contact Us" },
  ];

  const menuHtml = items
    .map(
      ({ id, href, label }) =>
        `<a href="${href}" class="nav-link${id === activePage ? " active" : ""}">${label}</a>`
    )
    .join("");

  root.innerHTML = `
    <a href="dashboard.html" class="brand" title="${brand}"><span>🌱</span><span class="brand-text">${brand}</span></a>
    <div class="menu">${menuHtml}</div>
  `;
}

// Google Translate Initialization for App-Wide Language Selection
function addGoogleTranslate() {
  const div = document.createElement('div');
  div.id = 'google_translate_element';
  div.style.display = 'none';
  document.body.appendChild(div);

  window.googleTranslateElementInit = function() {
    new google.translate.TranslateElement({
      pageLanguage: 'en',
      includedLanguages: 'en,hi',
      autoDisplay: false
    }, 'google_translate_element');
  };

  const script = document.createElement('script');
  script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
  document.head.appendChild(script);

  const style = document.createElement('style');
  style.innerHTML = `
    body { top: 0 !important; }
    .skiptranslate { display: none !important; }
  `;
  document.head.appendChild(style);

  // Sync the language dropdown if it exists on the page
  setTimeout(() => {
    const langSelect = document.querySelector('.lang-select');
    if (langSelect) {
      // Check current cookie
      const match = document.cookie.match(/googtrans=([^;]+)/);
      if (match && (match[1] === '/en/hi' || match[1] === '/auto/hi')) {
        langSelect.value = 'हिन्दी';
      } else {
        langSelect.value = 'English';
      }

      langSelect.addEventListener('change', (e) => {
        if (e.target.value === 'हिन्दी') {
          document.cookie = "googtrans=/en/hi; path=/";
        } else {
          document.cookie = "googtrans=/en/en; path=/";
        }
        window.location.reload();
      });
    }
  }, 100);
}

// Initialize on import
addGoogleTranslate();
