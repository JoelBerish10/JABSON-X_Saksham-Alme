/* ========================================================
   ServeLocal — Interactive UI Scripts
   Urban Company & Zepto Desktop Features
   ======================================================== */

// ── 1. Location Selection Modal ──
function openLocationModal() {
  const modal = document.getElementById('location-modal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    const input = document.getElementById('city-search-box');
    if (input) setTimeout(() => input.focus(), 100);
  }
}

function closeLocationModal(event) {
  const modal = document.getElementById('location-modal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

function selectCity(cityName) {
  const locText = document.getElementById('current-location-text');
  if (locText) {
    locText.textContent = cityName;
  }
  // Highlight active city
  document.querySelectorAll('.city-card').forEach(card => {
    card.classList.toggle('active', card.querySelector('.city-name')?.textContent === cityName.split(',')[0]);
  });
  closeLocationModal();
}

// Filter cities in modal
const citySearchBox = document.getElementById('city-search-box');
if (citySearchBox) {
  citySearchBox.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();
    document.querySelectorAll('.city-card').forEach(card => {
      const name = card.querySelector('.city-name')?.textContent.toLowerCase() || '';
      card.style.display = name.includes(query) ? 'flex' : 'none';
    });
  });
}

// ── 2. Global Search Bar & Keyboard Shortcut (⌘K / Ctrl+K) ──
const globalSearch = document.getElementById('global-search-input');
const searchDropdown = document.getElementById('search-dropdown');

if (globalSearch && searchDropdown) {
  globalSearch.addEventListener('focus', () => {
    searchDropdown.style.display = 'block';
  });

  globalSearch.addEventListener('input', (e) => {
    const val = e.target.value.toLowerCase().trim();
    const items = searchDropdown.querySelectorAll('.search-item');
    items.forEach(item => {
      const text = item.querySelector('.s-text')?.textContent.toLowerCase() || '';
      item.style.display = text.includes(val) ? 'flex' : 'none';
    });
  });

  document.addEventListener('click', (e) => {
    if (!document.getElementById('nav-search-bar')?.contains(e.target)) {
      searchDropdown.style.display = 'none';
    }
  });
}

// ⌘K / Ctrl+K listener
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    if (globalSearch) {
      globalSearch.focus();
      if (searchDropdown) searchDropdown.style.display = 'block';
    }
  }
  if (e.key === 'Escape') {
    closeLocationModal();
    if (searchDropdown) searchDropdown.style.display = 'none';
  }
});

// ── 3. Hamburger Navigation Toggle ──
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('nav-links');
if (hamburger && navLinks) {
  hamburger.addEventListener('click', () => {
    const isVisible = navLinks.style.display === 'flex';
    navLinks.style.display = isVisible ? 'none' : 'flex';
    if (!isVisible) {
      navLinks.style.flexDirection = 'column';
      navLinks.style.position = 'absolute';
      navLinks.style.top = '72px';
      navLinks.style.left = '0';
      navLinks.style.right = '0';
      navLinks.style.background = '#FFFFFF';
      navLinks.style.padding = '20px';
      navLinks.style.boxShadow = '0 10px 25px rgba(0,0,0,0.1)';
      navLinks.style.borderBottom = '1px solid #E2E8F0';
    } else {
      navLinks.removeAttribute('style');
    }
  });
}

// ── 4. Auto-dismiss Flash Messages ──
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity 0.3s, transform 0.3s';
    el.style.opacity = '0';
    el.style.transform = 'translateY(-10px)';
    setTimeout(() => el.remove(), 300);
  }, 4500);
});

// ── 5. Toggle Password Visibility ──
function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

// ── 6. File Upload Drag & Drop Preview ──
const uploadArea = document.getElementById('photo-upload-area');
if (uploadArea) {
  uploadArea.addEventListener('dragover', e => {
    e.preventDefault();
    uploadArea.style.borderColor = 'var(--clr-primary)';
    uploadArea.style.background = 'var(--clr-primary-subtle)';
  });
  uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = '';
    uploadArea.style.background = '';
  });
  uploadArea.addEventListener('drop', e => {
    e.preventDefault();
    uploadArea.style.borderColor = '';
    uploadArea.style.background = '';
    const file = e.dataTransfer.files[0];
    if (file) {
      const input = document.getElementById('photo');
      if (input) {
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.dispatchEvent(new Event('change'));
      }
    }
  });
}
