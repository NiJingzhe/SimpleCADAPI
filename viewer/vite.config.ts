import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      // The re-studio local server (viewer/server) owns the case state.
      '/api': 'http://127.0.0.1:7170',
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
        re: 're.html',
      },
    },
  },
});
