import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { API_OPERATION, collectNavigation, renderIndexes } from './docs-lib.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const entries = collectNavigation(JSON.parse(readFileSync(path.join(root, 'docs.json'), 'utf8')));
const preamble = readFileSync(path.join(root, 'scripts/llms-preamble.txt'), 'utf8');
const result = renderIndexes(entries, (route) => {
  const filename = path.join(root, `${route}.mdx`);
  return existsSync(filename) ? readFileSync(filename, 'utf8') : undefined;
}, preamble);
let stale = false;
for (const [filename, text] of [['llms.txt', result.index], ['llms-full.txt', result.full]]) {
  const target = path.join(root, filename);
  if (process.argv.includes('--check')) {
    if (!existsSync(target) || readFileSync(target, 'utf8') !== text) {
      console.error(`${filename} is stale; run npm run docs:index`);
      stale = true;
    }
  } else {
    writeFileSync(target, text);
    console.log(`Generated ${filename}`);
  }
}
if (stale) process.exitCode = 1;
const pages = entries.filter(({ route }) => !API_OPERATION.test(route));
const operate = pages.filter(({ route }) => route === 'operate' || route.startsWith('operate/'));
console.log(`${pages.length} local navigation pages; ${operate.length} Operate pages; ${entries.length - pages.length} external OpenAPI operations. Root metadata is not counted as a page.`);
