import type { ReactNode } from 'react';

import { useAuthToken } from '../lib/auth';
import AuthScreen from './AuthScreen';
import LockScreen from './LockScreen';

/**
 * Nothing in the app is shown until this device is logged in. Once logged in, the PIN
 * lock (if set) covers the app after it has been idle.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const token = useAuthToken();
  if (!token) return <AuthScreen />;
  return (
    <>
      {children}
      <LockScreen />
    </>
  );
}
