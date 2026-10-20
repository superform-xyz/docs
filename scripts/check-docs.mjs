import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { API_OPERATION, collectNavigation, validatePages } from './docs-lib.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const config = JSON.parse(readFileSync(path.join(root, 'docs.json'), 'utf8'));
const entries = collectNavigation(config);
const errors = [];
const seen = new Set();
for (const { route, openapi } of entries) {
  if (seen.has(route)) errors.push(`Duplicate navigation entry: ${route}`);
  seen.add(route);
  if (API_OPERATION.test(route)) {
    if (!openapi) errors.push(`Missing OpenAPI source: ${route}`);
  } else if (!existsSync(path.join(root, `${route}.mdx`))) {
    errors.push(`Missing navigation page: ${route}`);
  }
}
const pages = new Map();
function scan(dir) {
  for (const item of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (item.name.startsWith('.') || item.name === 'node_modules') continue;
    const filename = path.join(dir, item.name);
    if (item.isDirectory()) scan(filename);
    else if (item.name.endsWith('.mdx')) pages.set(path.relative(root, filename).replaceAll(path.sep, '/').slice(0, -4), readFileSync(filename, 'utf8'));
  }
}
scan(root);
for (const route of pages.keys()) {
  if ((route === 'operate' || route.startsWith('operate/')) && !seen.has(route)) errors.push(`Orphaned Operate page: ${route}`);
}
errors.push(...await validatePages(pages, (url) => {
  const filename = path.resolve(root, `.${url}`);
  return filename.startsWith(root) && existsSync(filename) && statSync(filename).isFile();
}));
const groups = config.navigation.tabs.find(({ tab }) => tab === 'Operate')?.groups.map(({ group }) => group);
if (JSON.stringify(groups) !== JSON.stringify(['Start', 'Configure', 'Strategies', 'Playbooks', 'Operations', 'Reference'])) errors.push('Operate must retain its six workflow groups');
const operate = entries.filter(({ route }) => route === 'operate' || route.startsWith('operate/'));
if (operate.length !== 39) errors.push(`Expected 39 Operate routes, got ${operate.length}`);
if (errors.length) {
  console.error(errors.join('\n'));
  console.error(`${errors.length} documentation error(s)`);
  process.exitCode = 1;
} else {
  console.log(`Compiled ${pages.size} MDX files; checked internal links, fragments, assets, JSON blocks, and navigation (${operate.length} Operate routes).`);
  console.log('Local compilation does not evaluate interactive components or verify external links/authenticated product actions. Run Mintlify validate for the platform build.');
}
