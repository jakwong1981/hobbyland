// mobile/capacitor.config.ts
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.hobbyland.pricecompare',
  appName: 'Gunpla 格價',
  // The production Vite bundle built by `scripts/build-mobile.sh` (frontend/dist).
  webDir: '../frontend/dist',
  server: {
    androidScheme: 'https',
  },
  android: {
    // The app UI is served from https://localhost; without this, API calls to
    // HTTP LAN backends (the documented dev setup) are blocked as mixed content.
    allowMixedContent: true,
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#05070a',
    },
    Keyboard: {
      resize: 'body',
    },
  },
};

export default config;
