import { defineConfig } from 'vite';
import path from 'path';

// Detect if running on Replit
const isReplit = process.env.REPLIT || process.env.REPL_SLUG;

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: isReplit ? 5000 : 3000,   // 5000 on Replit, 3000 locally
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
});
