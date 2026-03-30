import { initNavbar } from './components/navbar.js';
import { initModal } from './components/modal.js';
import { initLanding } from './pages/landing.js';
import { initChat } from './pages/chat.js';
import { initSupabase, getCurrentUser, onAuthChange } from './services/supabase.js';
import { checkAuth } from './utils/auth.js';

let currentView = 'landing';

async function initApp() {
    // Initialize Supabase
    await initSupabase();
    
    // Initialize components
    initNavbar();
    initModal();
    
    // Check auth status
    const user = await checkAuth();
    
    // Initialize landing page
    initLanding();
    
    // Listen for auth changes
    onAuthChange((user) => {
        if (user && currentView === 'landing') {
            // Auto-switch to chat if logged in and on landing
            document.getElementById('landingContent')?.remove();
            initChat();
            currentView = 'chat';
        } else if (!user && currentView === 'chat') {
            location.reload();
        }
    });
    
    // Handle "Try LawTalk" buttons from landing
    window.openChatFromLanding = () => {
        if (getCurrentUser()) {
            document.getElementById('landingContent')?.remove();
            initChat();
            currentView = 'chat';
        } else {
            window.showAuthModal();
        }
    };
}

// Start app when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}