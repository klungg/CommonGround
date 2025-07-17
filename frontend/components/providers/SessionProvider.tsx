'use client';

import React, { useEffect } from 'react';
import { reaction } from 'mobx';
import { sessionStore } from '@/app/stores/sessionStore';
import { toast } from 'sonner';

interface SessionProviderProps {
  children: React.ReactNode;
}

export function SessionProvider({ children }: SessionProviderProps) {
  useEffect(() => {
    // Initialize session and WebSocket connection on app startup
    console.log('SessionProvider: Initializing session and WebSocket connection');
    sessionStore.initializeSessionAndConnect();

    // Return a cleanup function to be called on app unmount
    return () => {
      console.log('SessionProvider: Cleaning up session and WebSocket connection');
      sessionStore.cleanup();
    };
  }, []); // Empty dependency array ensures this runs only on app startup and unmount

  // Global error handling - use MobX reaction to listen for changes to sessionStore.error
  useEffect(() => {
    const dispose = reaction(
      () => sessionStore.error,
      (error) => {
        if (error) {
          toast.error(error);
          sessionStore.error = null; // Clear the error state after displaying it
        }
      }
    );

    return dispose; // Cleanup the reaction
  }, []);

  return <>{children}</>;
} 