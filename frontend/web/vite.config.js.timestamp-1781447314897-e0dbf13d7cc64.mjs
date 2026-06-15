// vite.config.js
import { defineConfig } from "file:///Users/apple/Desktop/%E7%AD%BE%E8%AF%81%E9%A1%B9%E7%9B%AE/frontend/web/node_modules/vite/dist/node/index.js";
import vue from "file:///Users/apple/Desktop/%E7%AD%BE%E8%AF%81%E9%A1%B9%E7%9B%AE/frontend/web/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import AutoImport from "file:///Users/apple/Desktop/%E7%AD%BE%E8%AF%81%E9%A1%B9%E7%9B%AE/frontend/web/node_modules/unplugin-auto-import/dist/vite.js";
import Components from "file:///Users/apple/Desktop/%E7%AD%BE%E8%AF%81%E9%A1%B9%E7%9B%AE/frontend/web/node_modules/unplugin-vue-components/dist/vite.js";
import { ElementPlusResolver } from "file:///Users/apple/Desktop/%E7%AD%BE%E8%AF%81%E9%A1%B9%E7%9B%AE/frontend/web/node_modules/unplugin-vue-components/dist/resolvers.js";
import path from "node:path";
var __vite_injected_original_dirname = "/Users/apple/Desktop/\u7B7E\u8BC1\u9879\u76EE/frontend/web";
var vite_config_default = defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] })
  ],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "src"),
      "@shared": path.resolve(__vite_injected_original_dirname, "../shared")
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("vue/") || id.includes("vue-router") || id.includes("pinia")) {
              return "vue-vendor";
            }
            if (id.includes("element-plus")) {
              return "element-plus";
            }
            if (id.includes("vue-i18n") || id.includes("@shared/i18n")) {
              return "i18n";
            }
            if (id.includes("axios")) {
              return "axios-vendor";
            }
          }
        }
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvVXNlcnMvYXBwbGUvRGVza3RvcC9cdTdCN0VcdThCQzFcdTk4NzlcdTc2RUUvZnJvbnRlbmQvd2ViXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvVXNlcnMvYXBwbGUvRGVza3RvcC9cdTdCN0VcdThCQzFcdTk4NzlcdTc2RUUvZnJvbnRlbmQvd2ViL3ZpdGUuY29uZmlnLmpzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9Vc2Vycy9hcHBsZS9EZXNrdG9wLyVFNyVBRCVCRSVFOCVBRiU4MSVFOSVBMSVCOSVFNyU5QiVBRS9mcm9udGVuZC93ZWIvdml0ZS5jb25maWcuanNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJ1xuaW1wb3J0IHZ1ZSBmcm9tICdAdml0ZWpzL3BsdWdpbi12dWUnXG5pbXBvcnQgQXV0b0ltcG9ydCBmcm9tICd1bnBsdWdpbi1hdXRvLWltcG9ydC92aXRlJ1xuaW1wb3J0IENvbXBvbmVudHMgZnJvbSAndW5wbHVnaW4tdnVlLWNvbXBvbmVudHMvdml0ZSdcbmltcG9ydCB7IEVsZW1lbnRQbHVzUmVzb2x2ZXIgfSBmcm9tICd1bnBsdWdpbi12dWUtY29tcG9uZW50cy9yZXNvbHZlcnMnXG5pbXBvcnQgcGF0aCBmcm9tICdub2RlOnBhdGgnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtcbiAgICB2dWUoKSxcbiAgICBBdXRvSW1wb3J0KHsgcmVzb2x2ZXJzOiBbRWxlbWVudFBsdXNSZXNvbHZlcigpXSB9KSxcbiAgICBDb21wb25lbnRzKHsgcmVzb2x2ZXJzOiBbRWxlbWVudFBsdXNSZXNvbHZlcigpXSB9KVxuICBdLFxuICByZXNvbHZlOiB7XG4gICAgYWxpYXM6IHtcbiAgICAgICdAJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJ3NyYycpLFxuICAgICAgJ0BzaGFyZWQnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnLi4vc2hhcmVkJylcbiAgICB9XG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIGhvc3Q6ICcwLjAuMC4wJyxcbiAgICBwb3J0OiA1MTczLFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaSc6IHtcbiAgICAgICAgdGFyZ2V0OiAnaHR0cDovLzEyNy4wLjAuMTo4MDAwJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlXG4gICAgICB9XG4gICAgfVxuICB9LFxuICBidWlsZDoge1xuICAgIHJvbGx1cE9wdGlvbnM6IHtcbiAgICAgIG91dHB1dDoge1xuICAgICAgICBtYW51YWxDaHVua3MoaWQpIHtcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ25vZGVfbW9kdWxlcycpKSB7XG4gICAgICAgICAgICAvLyBWdWUgY29yZSBlY29zeXN0ZW0gXHUyMDE0IHN0YWJsZSwgY2FjaGVhYmxlIGluZGVwZW5kZW50bHlcbiAgICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygndnVlLycpIHx8IGlkLmluY2x1ZGVzKCd2dWUtcm91dGVyJykgfHwgaWQuaW5jbHVkZXMoJ3BpbmlhJykpIHtcbiAgICAgICAgICAgICAgcmV0dXJuICd2dWUtdmVuZG9yJ1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgLy8gRWxlbWVudCBQbHVzIFx1MjAxNCBsYXJnZXN0IGNodW5rLCBzZXBhcmF0ZSBmb3IgbG9uZy10ZXJtIGNhY2hpbmdcbiAgICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygnZWxlbWVudC1wbHVzJykpIHtcbiAgICAgICAgICAgICAgcmV0dXJuICdlbGVtZW50LXBsdXMnXG4gICAgICAgICAgICB9XG4gICAgICAgICAgICAvLyBpMThuICsgbG9jYWxlIGZpbGVzIFx1MjAxNCBsb2FkZWQgb25jZSwgY2FjaGVkXG4gICAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ3Z1ZS1pMThuJykgfHwgaWQuaW5jbHVkZXMoJ0BzaGFyZWQvaTE4bicpKSB7XG4gICAgICAgICAgICAgIHJldHVybiAnaTE4bidcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIC8vIEhUVFAgY2xpZW50XG4gICAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ2F4aW9zJykpIHtcbiAgICAgICAgICAgICAgcmV0dXJuICdheGlvcy12ZW5kb3InXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuICB9XG59KSJdLAogICJtYXBwaW5ncyI6ICI7QUFBb1UsU0FBUyxvQkFBb0I7QUFDalcsT0FBTyxTQUFTO0FBQ2hCLE9BQU8sZ0JBQWdCO0FBQ3ZCLE9BQU8sZ0JBQWdCO0FBQ3ZCLFNBQVMsMkJBQTJCO0FBQ3BDLE9BQU8sVUFBVTtBQUxqQixJQUFNLG1DQUFtQztBQU96QyxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTO0FBQUEsSUFDUCxJQUFJO0FBQUEsSUFDSixXQUFXLEVBQUUsV0FBVyxDQUFDLG9CQUFvQixDQUFDLEVBQUUsQ0FBQztBQUFBLElBQ2pELFdBQVcsRUFBRSxXQUFXLENBQUMsb0JBQW9CLENBQUMsRUFBRSxDQUFDO0FBQUEsRUFDbkQ7QUFBQSxFQUNBLFNBQVM7QUFBQSxJQUNQLE9BQU87QUFBQSxNQUNMLEtBQUssS0FBSyxRQUFRLGtDQUFXLEtBQUs7QUFBQSxNQUNsQyxXQUFXLEtBQUssUUFBUSxrQ0FBVyxXQUFXO0FBQUEsSUFDaEQ7QUFBQSxFQUNGO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsUUFDTixRQUFRO0FBQUEsUUFDUixjQUFjO0FBQUEsTUFDaEI7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsT0FBTztBQUFBLElBQ0wsZUFBZTtBQUFBLE1BQ2IsUUFBUTtBQUFBLFFBQ04sYUFBYSxJQUFJO0FBQ2YsY0FBSSxHQUFHLFNBQVMsY0FBYyxHQUFHO0FBRS9CLGdCQUFJLEdBQUcsU0FBUyxNQUFNLEtBQUssR0FBRyxTQUFTLFlBQVksS0FBSyxHQUFHLFNBQVMsT0FBTyxHQUFHO0FBQzVFLHFCQUFPO0FBQUEsWUFDVDtBQUVBLGdCQUFJLEdBQUcsU0FBUyxjQUFjLEdBQUc7QUFDL0IscUJBQU87QUFBQSxZQUNUO0FBRUEsZ0JBQUksR0FBRyxTQUFTLFVBQVUsS0FBSyxHQUFHLFNBQVMsY0FBYyxHQUFHO0FBQzFELHFCQUFPO0FBQUEsWUFDVDtBQUVBLGdCQUFJLEdBQUcsU0FBUyxPQUFPLEdBQUc7QUFDeEIscUJBQU87QUFBQSxZQUNUO0FBQUEsVUFDRjtBQUFBLFFBQ0Y7QUFBQSxNQUNGO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFDRixDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
