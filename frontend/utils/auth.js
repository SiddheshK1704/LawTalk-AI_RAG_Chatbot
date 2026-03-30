    import { signUp, signIn, getCurrentUser, onAuthChange } from '../services/supabase.js';

export async function handleAuth(email, password) {
    if (!email || !password) {
        alert('Please enter both email and password');
        return false;
    }
    
    try {
        // Try to sign in first, if fails, sign up
        let user;
        try {
            user = await signIn(email, password);
        } catch (error) {
            if (error.message.includes('Invalid login credentials')) {
                user = await signUp(email, password);
            } else {
                throw error;
            }
        }
        return !!user;
    } catch (error) {
        console.error('Auth error:', error);
        alert(error.message || 'Authentication failed');
        return false;
    }
}

export async function checkAuth() {
    return getCurrentUser();
}

export function requireAuth(callback) {
    if (getCurrentUser()) {
        callback();
    } else {
        window.showAuthModal();
    }
}