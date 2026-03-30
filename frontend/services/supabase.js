import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

const SUPABASE_URL = 'https://your-project.supabase.co'; // Replace with your URL
const SUPABASE_ANON_KEY = 'your-anon-key'; // Replace with your anon key

let supabase = null;
let currentUser = null;
let authListeners = [];

export async function initSupabase() {
    if (!SUPABASE_URL.includes('your-project')) {
        supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        
        // Check current session
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
            currentUser = session.user;
        }
        
        // Listen for auth changes
        supabase.auth.onAuthStateChange((event, session) => {
            currentUser = session?.user || null;
            authListeners.forEach(listener => listener(currentUser));
        });
    } else {
        console.warn('Supabase not configured. Using localStorage fallback.');
        // Mock auth for demo
        const stored = localStorage.getItem('lawtalk_user');
        if (stored) currentUser = JSON.parse(stored);
    }
}

export function getCurrentUser() {
    return currentUser;
}

export function onAuthChange(callback) {
    authListeners.push(callback);
    callback(currentUser);
}

export async function signUp(email, password) {
    if (supabase) {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        return data.user;
    } else {
        const mockUser = { id: btoa(email), email };
        localStorage.setItem('lawtalk_user', JSON.stringify(mockUser));
        currentUser = mockUser;
        return mockUser;
    }
}

export async function signIn(email, password) {
    if (supabase) {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        return data.user;
    } else {
        const mockUser = { id: btoa(email), email };
        localStorage.setItem('lawtalk_user', JSON.stringify(mockUser));
        currentUser = mockUser;
        return mockUser;
    }
}

export async function signOut() {
    if (supabase) {
        await supabase.auth.signOut();
    } else {
        localStorage.removeItem('lawtalk_user');
        currentUser = null;
    }
}

export async function saveChatMessage(userId, query, response) {
    if (supabase) {
        const { error } = await supabase
            .from('chat_messages')
            .insert({ user_id: userId, query, response, created_at: new Date() });
        if (error) console.error('Save error:', error);
    } else {
        const key = `lawtalk_chat_${userId}`;
        const existing = JSON.parse(localStorage.getItem(key) || '[]');
        existing.push({ query, response, timestamp: Date.now() });
        localStorage.setItem(key, JSON.stringify(existing));
    }
}

export async function getChatHistory(userId) {
    if (supabase) {
        const { data, error } = await supabase
            .from('chat_messages')
            .select('*')
            .eq('user_id', userId)
            .order('created_at', { ascending: true });
        if (error) return [];
        return data;
    } else {
        const key = `lawtalk_chat_${userId}`;
        return JSON.parse(localStorage.getItem(key) || '[]');
    }
}