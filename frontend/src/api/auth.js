import client from './client';

export const authApi = {
  login: async (email, password) => {
    // Determine if using FormData or JSON based on backend implementation
    // Plan used JSON: {email, password} -> /auth/login
    // But router also supports /auth/token with FormData. 
    // Let's use JSON endpoint /auth/login for simplicity in React
    const response = await client.post('/auth/login', { email, password });
    return response.data;
  },

  signup: async (userData) => {
    const response = await client.post('/auth/signup', userData);
    return response.data;
  },

  me: async () => {
    const response = await client.get('/auth/me');
    return response.data;
  }
};
