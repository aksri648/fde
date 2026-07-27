/**
 * Clerk integration for SolidJS.
 *
 * Uses @clerk/clerk-js directly (the vanilla JS SDK) since there's no official
 * SolidJS adapter. Exposes reactive signals for auth state and helper methods
 * for getting session tokens.
 */

import { Clerk } from "@clerk/clerk-js";
import { createSignal } from "solid-js";

let clerkInstance: Clerk | null = null;

const [isLoaded, setIsLoaded] = createSignal(false);
const [isSignedIn, setIsSignedIn] = createSignal(false);
const [user, setUser] = createSignal<any>(null);

export { isLoaded, isSignedIn, user };

/**
 * Initialize Clerk. Call once at app startup.
 */
export async function initClerk(): Promise<Clerk> {
  const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
  if (!publishableKey) {
    console.warn("VITE_CLERK_PUBLISHABLE_KEY not set — auth disabled (dev mode)");
    setIsLoaded(true);
    setIsSignedIn(true); // allow access in dev without Clerk
    setUser({ id: "dev-user", firstName: "Dev", lastName: "User" });
    return null as any;
  }

  const clerk = new Clerk(publishableKey);
  await clerk.load();
  clerkInstance = clerk;

  // Set initial state
  setIsLoaded(true);
  setIsSignedIn(!!clerk.user);
  setUser(clerk.user);

  // Listen for auth state changes
  clerk.addListener((emission) => {
    setIsSignedIn(!!emission.user);
    setUser(emission.user);
  });

  return clerk;
}

/**
 * Get the Clerk instance (after init).
 */
export function getClerk(): Clerk | null {
  return clerkInstance;
}

/**
 * Get the current session token for API calls.
 * Returns the JWT that should be sent as `Authorization: Bearer <token>`.
 */
export async function getSessionToken(): Promise<string> {
  if (!clerkInstance) {
    // Dev mode fallback
    return import.meta.env.VITE_FDE_API_KEY || "dev-token";
  }
  const session = clerkInstance.session;
  if (!session) return "";
  const token = await session.getToken();
  return token || "";
}

/**
 * Mount the Clerk Sign-In UI into a DOM element.
 */
export function mountSignIn(el: HTMLDivElement) {
  clerkInstance?.mountSignIn(el, {
    routing: "hash",
  });
}

/**
 * Mount the Clerk Sign-Up UI into a DOM element.
 */
export function mountSignUp(el: HTMLDivElement) {
  clerkInstance?.mountSignUp(el, {
    routing: "hash",
  });
}

/**
 * Mount the Clerk User Button into a DOM element.
 */
export function mountUserButton(el: HTMLDivElement) {
  clerkInstance?.mountUserButton(el);
}

/**
 * Sign out the current user.
 */
export async function signOut() {
  await clerkInstance?.signOut();
}
