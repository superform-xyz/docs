import { parseDocument } from 'yaml';
import { compile } from '@mdx-js/mdx';
import remarkGfm from 'remark-gfm';
import GithubSlugger from 'github-slugger';

// Parse data-only YAML. Never dispatch a frontmatter language to an engine.
function matter(raw) {
  const normalized = raw.replace(/^\uFEFF/, '').replaceAll('\r\n', '\n');
  if (!normalized.startsWith('---')) return { data: {}, content: normalized };
  if (!/^---[ \t]*\n/.test(normalized)) throw new Error('Invalid frontmatter: only YAML delimiters are allowed');
  const match = /^---[ \t]*\n([\s\S]*?)\n---[ \t]*(?:\n|$)/.exec(normalized);
  if (!match) throw new Error('Invalid frontmatter: missing closing delimiter');
  const doc = parseDocument(match[1], { schema: 'core', customTags: [], uniqueKeys: true });
  // Unknown tags are warnings in yaml; rejecting warnings is essential.
  if (doc.errors.length || doc.warnings.length) {
    throw new Error(`Invalid frontmatter: ${[...doc.errors, ...doc.warnings].map((e) => e.message).join('; ')}`);
  }
  let data;
  try { data = doc.toJS({ maxAliasCount: 50 }); }
  catch (error) { throw new Error(`Invalid frontmatter: ${error.message}`); }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid frontmatter: expected a mapping');
  return { data, content: normalized.slice(match[0].length) };
}

export async function validatePages(pages, assetExists) {
  const errors = [];
  const links = [];
  const anchors = new Map();
  for (const [route, raw] of pages) {
    const ids = new Set();
    anchors.set(route, ids);
    const slugger = new GithubSlugger();
    const definitions = new Map();
    const references = [];
    const text = (node) => node.value ?? (node.children ?? []).map(text).join('');
    const inspect = () => (tree) => {
      const visit = (node) => {
        if (node.type === 'heading') ids.add(slugger.slug(text(node)));
        if (node.type === 'link' || node.type === 'image') links.push({ route, url: node.url });
        if (node.type === 'definition') definitions.set(node.identifier, node.url);
        if (node.type === 'linkReference' || node.type === 'imageReference') references.push(node.identifier);
        for (const attr of node.attributes ?? []) {
          if (typeof attr.value !== 'string') continue;
          if (attr.name === 'href' || attr.name === 'src') links.push({ route, url: attr.value });
          if (attr.name === 'id') ids.add(attr.value);
        }
        if (node.type === 'code' && node.lang === 'json') {
          try { JSON.parse(node.value); }
          catch (error) { errors.push(`${route}: JSON block: ${error.message}`); }
        }
        for (const child of node.children ?? []) visit(child);
      };
      visit(tree);
      for (const id of references) {
        if (definitions.has(id)) links.push({ route, url: definitions.get(id) });
        else errors.push(`${route}: unresolved link reference ${id}`);
      }
    };
    try {
      const { data, content } = matter(raw);
      if (!data.title) errors.push(`${route}: missing title`);
      await compile(content, { remarkPlugins: [remarkGfm, inspect] });
    } catch (error) {
      errors.push(`${route}: MDX: ${error.message}`);
    }
  }
  for (const { route, url } of links) {
    let parsed;
    try { parsed = new URL(url, `https://docs.superform.xyz/${route === 'index' ? '' : route}`); }
    catch { errors.push(`${route}: invalid link ${url}`); continue; }
    if (parsed.origin !== 'https://docs.superform.xyz') continue;
    let target = decodeURIComponent(parsed.pathname).replace(/^\/|\/$/g, '').replace(/\.mdx?$/, '') || 'index';
    if (!pages.has(target) && pages.has(`${target}/index`)) target += '/index';
    if (!pages.has(target)) {
      if (!assetExists(decodeURIComponent(parsed.pathname))) errors.push(`${route}: missing link target ${url}`);
    } else if (parsed.hash && !anchors.get(target)?.has(decodeURIComponent(parsed.hash.slice(1)))) {
      errors.push(`${route}: missing fragment ${url}`);
    }
  }
  return errors;
}


export const API_OPERATION = /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \/\S+$/;

export function renderIndexes(entries, readPage, preamble) {
  const invalidNotes = [
    /pendingRedeemRequest\(\s*account\s*\)/,
    /Index 0 is `approve`, index 1 is `deposit`/,
    /`reward_rate` is the primary yield today/,
  ];
  if (invalidNotes.some((pattern) => pattern.test(preamble))) {
    throw new Error('Invalid agent notes: outdated ABI, fixed execution ordering, or undated yield claim');
  }
  const index = [preamble.trimEnd(), ''];
  const full = [preamble.trimEnd(), ''];
  const seen = new Set();
  let section;
  for (const entry of entries) {
    if (seen.has(entry.route)) throw new Error(`Duplicate navigation page: ${entry.route}`);
    seen.add(entry.route);
    if (entry.section !== section) {
      section = entry.section;
      index.push(`## ${section}`, '');
    }
    if (API_OPERATION.test(entry.route)) {
      if (!entry.openapi) throw new Error(`Missing OpenAPI source: ${entry.route}`);
      index.push(`- \`${entry.route}\`: [OpenAPI contract](${entry.openapi}).`);
      full.push(`## ${entry.route}`, `Source: ${entry.openapi}`, '',
        'Navigation entry backed by the external OpenAPI contract. Schema content is not embedded in this local MDX corpus.', '', '---', '');
      continue;
    }
    const raw = readPage(entry.route);
    if (typeof raw !== 'string') throw new Error(`Missing page: ${entry.route}`);
    const { data, content } = matter(raw);
    if (!data.title) throw new Error(`Missing title: ${entry.route}`);
    const url = `https://docs.superform.xyz/${entry.route === 'index' ? '' : entry.route}`;
    index.push(`- [${data.title}](${url}): ${data.description ?? data.title}`);
    full.push(`# ${data.title}`, `Source: ${url}`, '', content.trim(), '', '---', '');
  }
  return { index: `${index.join('\n').trimEnd()}\n`, full: `${full.join('\n').trimEnd()}\n` };
}

export function collectNavigation(config) {
  const entries = [];
  const walk = (node, section = [], openapi = config.openapi) => {
    if (typeof node === 'string') {
      entries.push({ route: node, section: section.join(' / '), openapi });
      return;
    }
    if (Array.isArray(node)) {
      for (const child of node) walk(child, section, openapi);
      return;
    }
    if (!node || typeof node !== 'object') return;
    const label = node.tab ?? node.group;
    const labels = label ? [...section, label] : section;
    const schema = node.openapi ?? openapi;
    for (const key of ['tabs', 'groups', 'pages']) {
      if (node[key]) walk(node[key], labels, schema);
    }
  };
  walk(config.navigation);
  return entries;
}
