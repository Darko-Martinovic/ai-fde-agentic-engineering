/** Settings the dashboard is built with, from settings/.env.defaults and, for
 *  `npm run dev`, .env. */
interface ImportMetaEnv {
  /** The most claim agents a run may have at once. */
  readonly VITE_MAX_AGENTS: string;
  /** The Supabase project handlers sign in through, and its publishable key. */
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_PUBLISHABLE_KEY: string;
}
