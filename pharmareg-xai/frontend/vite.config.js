import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{proxy:{'/api':'http://127.0.0.1:8010','/health':'http://127.0.0.1:8010'}},build:{rollupOptions:{output:{manualChunks:{charts:['recharts'],validation:['zod'],query:['@tanstack/react-query']}}}},test:{include:['src/**/*.test.{js,jsx}'],environment:'jsdom',globals:true}});
