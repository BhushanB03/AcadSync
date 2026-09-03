/**
 * AcadSync - Theme Toggle & UI Interactions
 * Phase 10: UI/UX Overhaul
 */

(function () {
    'use strict';

    const STORAGE_KEY = 'acadsync-theme';
    const THEME_DARK = 'dark';
    const THEME_LIGHT = 'light';

    /**
     * Get currently stored theme or default to dark
     */
    function getStoredTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored === THEME_LIGHT || stored === THEME_DARK) {
            return stored;
        }
        return THEME_DARK;
    }

    /**
     * Apply theme to the document and update button state
     */
    function applyTheme(theme) {
        if (theme === THEME_LIGHT) {
            document.documentElement.setAttribute('data-theme', THEME_LIGHT);
        } else {
            document.documentElement.removeAttribute('data-theme');
        }

        updateToggleButtonUI(theme);
    }

    /**
     * Update the toggle button icon and text label
     */
    function updateToggleButtonUI(theme) {
        const toggleBtn = document.getElementById('themeToggleBtn');
        if (!toggleBtn) return;

        const iconContainer = toggleBtn.querySelector('.theme-toggle-icon');
        const textContainer = toggleBtn.querySelector('.theme-toggle-text');

        if (theme === THEME_LIGHT) {
            // In Light mode, show Moon icon and "Dark mode"
            if (iconContainer) {
                iconContainer.innerHTML = `
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                `;
            }
            if (textContainer) {
                textContainer.textContent = 'Dark mode';
            }
            toggleBtn.setAttribute('aria-label', 'Switch to dark theme');
        } else {
            // In Dark mode, show Sun icon and "Light mode"
            if (iconContainer) {
                iconContainer.innerHTML = `
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="1" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                `;
            }
            if (textContainer) {
                textContainer.textContent = 'Light mode';
            }
            toggleBtn.setAttribute('aria-label', 'Switch to light theme');
        }
    }

    /**
     * Toggle theme between dark and light
     */
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') === THEME_LIGHT ? THEME_LIGHT : THEME_DARK;
        const newTheme = currentTheme === THEME_LIGHT ? THEME_DARK : THEME_LIGHT;

        localStorage.setItem(STORAGE_KEY, newTheme);
        applyTheme(newTheme);
    }

    // Initialize when DOM is ready
    function init() {
        const currentTheme = getStoredTheme();
        applyTheme(currentTheme);

        const toggleBtn = document.getElementById('themeToggleBtn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', toggleTheme);
        }

        // Setup mobile sidebar toggle handlers
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');
        const sidebar = document.getElementById('appSidebar');
        const overlay = document.getElementById('mobileOverlay');

        if (mobileMenuBtn && sidebar && overlay) {
            mobileMenuBtn.addEventListener('click', function () {
                sidebar.classList.toggle('open');
                overlay.classList.toggle('open');
            });

            overlay.addEventListener('click', function () {
                sidebar.classList.remove('open');
                overlay.classList.remove('open');
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
