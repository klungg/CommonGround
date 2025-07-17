// Dynamically get the API base URL
const getApiBaseUrl = (): string => {
  // If the environment variable is set, prioritize it
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // In a browser environment, use the current page's origin as the API base URL
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  
  // Default value for server-side rendering
  return 'http://localhost:8000';
};

// Dynamically get the WebSocket URL
const getWebSocketUrl = (): string => {
  // If the environment variable is set, prioritize it
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  
  // In a browser environment, construct the WebSocket URL from the current page's protocol and host
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}`;
  }
  
  // Default value for server-side rendering
  return 'ws://localhost:8000';
};

export const config = {
  api: {
    baseUrl: getApiBaseUrl(),
  },
  ws: {
    url: getWebSocketUrl(),
    endpoint: '/ws',
  },
} as const;

export type Config = typeof config; 
