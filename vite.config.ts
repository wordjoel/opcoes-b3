import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

// Nenhuma chave entra no bundle: tudo que depende de segredo fica na API.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Separa as bibliotecas grandes para que uma mudança na interface não
        // invalide todo o bundle baixado pelo navegador.
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return 'react-vendor';
          if (/node_modules[\\/](lightweight-charts)[\\/]/.test(id)) return 'price-charts';
          if (/node_modules[\\/](recharts|d3-|victory-vendor)/.test(id)) return 'charts';
          if (/node_modules[\\/](lucide-react)[\\/]/.test(id)) return 'icons';
        },
      },
    },
  },
});
