const themeToggle = document.getElementById('themeToggle');
const profileButton = document.getElementById('profileButton');
const profileMenu = document.getElementById('profileMenu');

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    themeToggle.textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
  });
}

if (profileButton && profileMenu) {
  profileButton.addEventListener('click', () => {
    profileMenu.style.display = profileMenu.style.display === 'block' ? 'none' : 'block';
  });
}

window.addEventListener('click', (event) => {
  if (!profileMenu) return;
  if (!event.target.closest('.profile')) {
    profileMenu.style.display = 'none';
  }
});

const miniChartEl = document.getElementById('miniChart');
if (miniChartEl && typeof Chart !== 'undefined') {
  const ctx = miniChartEl.getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      datasets: [{
        label: 'Crop Health Score',
        data: [65, 59, 80, 81, 56, 55, 40],
        borderColor: '#f8b400',
        backgroundColor: 'rgba(248, 180, 0, 0.1)',
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(255, 255, 255, 0.1)'
          },
          ticks: {
            color: '#cbd5e1'
          }
        },
        x: {
          grid: {
            color: 'rgba(255, 255, 255, 0.1)'
          },
          ticks: {
            color: '#cbd5e1'
          }
        }
      }
    }
  });
}

async function fetchWeather() {
  const s1 = document.querySelector('.status-card:nth-child(1) .status-value');
  const s2 = document.querySelector('.status-card:nth-child(2) .status-value');
  if (!s1 || !s2) return;
  const cacheKey = 'agritech_weather_cache';
  const cacheMaxAgeMs = 30 * 60 * 1000;

  function applyWeather(data) {
    const temp = data.current_weather.temperature;
    const humidity = Math.floor(Math.random() * 20) + 60;
    s1.textContent = `${temp}°C in field 5`;
    s2.textContent = `${humidity}% near greenhouse`;
  }

  try {
    const cachedRaw = localStorage.getItem(cacheKey);
    if (cachedRaw) {
      const cached = JSON.parse(cachedRaw);
      if (
        cached &&
        cached.data &&
        typeof cached.ts === 'number' &&
        Date.now() - cached.ts < cacheMaxAgeMs
      ) {
        applyWeather(cached.data);
        return;
      }
    }

    const response = await fetch('https://api.open-meteo.com/v1/forecast?latitude=19.0760&longitude=72.8777&current_weather=true');
    const data = await response.json();
    localStorage.setItem(cacheKey, JSON.stringify({ data, ts: Date.now() }));
    applyWeather(data);
  } catch (error) {
    console.log('Weather API error:', error);
  }
}

fetchWeather();

function startVoice() {
  if (!('speechSynthesis' in window)) {
    alert('Voice assistant is not supported in this browser.');
    return;
  }
  const el = document.getElementById('voiceWaveform');
  const text = 'Welcome to AgriTech — Smart Crop Detective. Use the search bar to find crop diseases, fertilizers, or weather advice. Press Start Detection to scan your crop.';
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-US';
  speechSynthesis.speak(utterance);

  if (el) {
    el.style.display = 'flex';
    setTimeout(() => {
      el.style.display = 'none';
    }, 5000);
  }
}

function startScan() {
  const el = document.getElementById('cameraScan');
  if (!el) return;
  el.classList.remove('hidden');
  setTimeout(() => {
    el.classList.add('hidden');
  }, 3000);
}

function uploadImage() {
  startScan();
}

document.addEventListener('DOMContentLoaded', () => {
  const cropIcons = document.querySelectorAll('.crop-icon');
  cropIcons.forEach((icon, index) => {
    icon.style.animationDelay = `${index * 0.5}s`;
  });
});
