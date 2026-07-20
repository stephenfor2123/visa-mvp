import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/*.png'],
      manifest: false, // 使用 public/manifest.json
      devOptions: {
        enabled: false
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 }
            }
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 }
            }
          }
          // D-08: deliberately do NOT cache /api/* — auth + PII must not enter SW Cache Storage
        ]
      }
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@shared': path.resolve(__dirname, '../shared')
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern',
        silenceDeprecations: ['legacy-js-api', 'import', 'global-builtin'],
      }
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['htexvisa.com', 'www.htexvisa.com', '.htexvisa.com'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // Vue core ecosystem — stable, cacheable independently
            if (id.includes('vue/') || id.includes('vue-router') || id.includes('pinia')) {
              return 'vue-vendor'
            }
            // Element Plus — 合并到 vue-vendor 避免 TDZ 错误 (W18-1 修)
            // 之前单独拆 chunk 会触发 unplugin-vue-components + Element PlusResolver
            // 的 dynamic import 顺序问题，浏览器报 "Cannot access 'ye' before initialization"
            if (id.includes('element-plus')) {
              return 'vue-vendor'
            }
            // i18n — 合并到 vue-vendor (W18-2 修)
            // 之前单独拆 i18n chunk 触发 Vue I18n 9 内部 compose 函数丢失，
            // 浏览器报 "SyntaxError at i18n-*.js" + OrderNew 初始化失败
            if (id.includes('vue-i18n') || id.includes('@shared/i18n')) {
              return 'vue-vendor'
            }
            // HTTP client
            if (id.includes('axios')) {
              return 'axios-vendor'
            }
          }
        }
      }
    }
  }
})