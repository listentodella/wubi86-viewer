import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: false,
      includeAssets: ['favicon.svg', 'apple-touch-icon.png', 'fonts/zhengkai-roots.json'],
      manifest: {
        name: '五笔字根图解 · 86 版',
        short_name: '五笔图解',
        description: '输入汉字、词语或编码，田字格高亮字根，自动讲解取码规则。',
        lang: 'zh-CN',
        theme_color: '#f7f3ea',
        background_color: '#f7f3ea',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // app shell + the two small data files that every page needs
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webmanifest,woff2}', 'data/roots.json', 'data/tiers.json'],
        // data.ts appends ?v=<DATA_VERSION>; ignore it when matching the precache
        ignoreURLParametersMatching: [/^v$/, /^utm_/, /^fbclid$/],
        navigateFallback: 'index.html',
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // the rest of /data is fetched on demand: cache first, refresh in background
            urlPattern: ({ url }: { url: URL }) => url.pathname.startsWith('/data/') && url.pathname.endsWith('.json'),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'wubi-data',
              expiration: { maxEntries: 800, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
})
