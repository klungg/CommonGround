'use client';

import React, { useEffect } from 'react';
import { projectStore } from '@/app/stores/projectStore';

interface AppProviderProps {
  children: React.ReactNode;
}

export function AppProvider({ children }: AppProviderProps) {
  useEffect(() => {
    // Initialize project data on app startup
    console.log('AppProvider: Initializing project store');
    projectStore.initialize();
  }, []); // Empty dependency array ensures this runs only once on app startup

  return <>{children}</>;
} 