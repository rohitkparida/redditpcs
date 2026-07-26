import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  output: 'static',
  integrations: [tailwind()],
  site: process.env.GITHUB_ACTIONS ? 'https://rohitkparida.github.io/redditpcs' : 'https://redditpcs.com',
  base: process.env.GITHUB_ACTIONS ? '/redditpcs' : undefined
});
