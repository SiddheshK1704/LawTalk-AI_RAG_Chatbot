export function initNavbar() {
    const navbarHTML = `
        <nav id="navbar" class="fixed top-0 left-0 w-full z-50 glass rounded-none border-x-0 border-t-0 px-6 md:px-12 py-4 transition-all duration-300">
            <div class="max-w-7xl mx-auto flex justify-between items-center">
                <div class="text-2xl font-bold tracking-tight bg-gradient-to-r from-white to-blue-300 bg-clip-text text-transparent">LawTalk</div>
                <div class="flex gap-3 md:gap-5 items-center">
                    <button id="navLoginBtn" class="text-sm md:text-base font-medium text-gray-200 hover:text-white transition px-3 py-2 rounded-xl hover:bg-white/10 btn-glow">Login / Signup</button>
                    <button id="navTryBtn" class="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white px-5 py-2 rounded-full text-sm md:text-base font-semibold shadow-lg btn-glow transition-all">Try LawTalk</button>
                </div>
            </div>
        </nav>
    `;
    
    document.body.insertAdjacentHTML('afterbegin', navbarHTML);
    
    // Event listeners
    document.getElementById('navLoginBtn')?.addEventListener('click', () => window.showAuthModal());
    document.getElementById('navTryBtn')?.addEventListener('click', () => {
        if (window.openChatFromLanding) window.openChatFromLanding();
    });
}