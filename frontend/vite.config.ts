// frontend/vite.config.ts
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend serves HTTPS only when ../certs exists (scripts/generate-cert.sh);
// mirror its own fallback so `pnpm dev` works either way.
const certsDir = resolve(import.meta.dirname, '../certs');
const backendTarget =
  existsSync(resolve(certsDir, 'server.pem')) && existsSync(resolve(certsDir, 'server-key.pem'))
    ? 'https://localhost:8089'
    : 'http://localhost:8089';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // secure:false accepts the self-signed certificate.
        target: backendTarget,
        secure: false,
      },
    },
  },
});
