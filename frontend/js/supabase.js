// Supabase client setup
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

// TODO: Replace with your Supabase project credentials
export const SUPABASE_URL = 'https://cqbmnahmfcrqgurgevhw.supabase.co';
export const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxYm1uYWhtZmNycWd1cmdldmh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQyODIwNDMsImV4cCI6MjA4OTg1ODA0M30.a8GDcdjcwrzdQUOnpJUuSJBm9c-ovMOE-riZYcNipbw';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
});
