import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const originalOperateRoutes = [
  'operate', 'operate/concepts', 'operate/prerequisites', 'operate/authentication',
  'operate/permissions', 'operate/quickstart', 'operate/ui/home', 'operate/ui/create-vault',
  'operate/ui/setup-checklist', 'operate/ui/dashboard', 'operate/ui/strategy',
  'operate/strategy/quickstart', 'operate/strategy/dsl', 'operate/strategy/action-config',
  'operate/strategy/troubleshooting', 'operate/strategy/anti-patterns',
  'operate/ui/simulation', 'operate/ui/intent-history', 'operate/ui/yield-sources',
  'operate/ui/merkle-trees', 'operate/ui/vault-settings', 'operate/ui/user-management',
  'operate/ui/distribute', 'operate/ui/pause', 'operate/automation/overview',
  'operate/automation/monitoring', 'operate/automation/webhooks', 'operate/api/overview',
  'operate/api/erebor', 'operate/api/strategy', 'operate/api/oms',
];

test('Operate navigation preserves the original routes and the approved additions', async () => {
  const { collectNavigation } = await import('./docs-lib.mjs');
  const config = JSON.parse(readFileSync(new URL('../docs.json', import.meta.url), 'utf8'));
  const actual = collectNavigation(config).map(({ route }) => route).filter((route) => route === 'operate' || route.startsWith('operate/'));
  const expected = [...originalOperateRoutes,
    'operate/strategy/variables', 'operate/strategy/lifecycle',
    'operate/playbooks/reserves', 'operate/playbooks/carry',
    'operate/playbooks/deleverage', 'operate/playbooks/redemptions',
    'operate/ui/execution-accounts', 'operate/ui/funding',
  ];
  assert.deepEqual(actual.toSorted(), expected.toSorted());
});


test('navigation visits nested pages once without counting root metadata', async () => {
  const { collectNavigation } = await import('./docs-lib.mjs');
  const entries = collectNavigation({ navigation: { tabs: [{ tab: 'Operate', groups: [
    { group: 'Start', root: 'operate', pages: ['operate', { group: 'Nested', pages: ['operate/access'] }] },
  ] }, { tab: 'API', groups: [{ group: 'Reads', openapi: 'https://example.org/schema.json', pages: ['GET /vaults'] }] }] } });
  assert.deepEqual(entries.map(({ route }) => route), ['operate', 'operate/access', 'GET /vaults']);
  assert.equal(entries[1].section, 'Operate / Start / Nested');
  assert.equal(entries[2].openapi, 'https://example.org/schema.json');
});

test('indexes preserve notes and render every page in nav order deterministically', async () => {
  const { renderIndexes } = await import('./docs-lib.mjs');
  const entries = [
    { route: 'index', section: 'Learn / Start' },
    { route: 'operate', section: 'Operate / Start' },
    { route: 'GET /vaults', section: 'API / Reads', openapi: 'https://example.org/schema.json' },
  ];
  const pages = new Map([
    ['index', '---\ntitle: "Home"\ndescription: "Home description"\n---\n\nHome body.\n'],
    ['operate', '---\ntitle: "Operate"\ndescription: "Operate description"\n---\n\nOperate body.\n'],
  ]);
  const notes = '# Docs\n\n## Notes for LLM Agents\n\n- Keep this unchanged.\n';
  const result = renderIndexes(entries, (route) => pages.get(route), notes);
  assert.deepEqual(result, renderIndexes(entries, (route) => pages.get(route), notes));
  assert.ok(result.index.startsWith(notes));
  assert.ok(result.full.startsWith(notes));
  assert.match(result.index, /\[Home\]\(https:\/\/docs.superform.xyz\/\)/);
  assert.match(result.full, /Source: https:\/\/docs.superform.xyz\/operate\n/);
  assert.ok(result.full.indexOf('Home body.') < result.full.indexOf('Operate body.'));
  assert.ok(!result.full.includes('title:'));
  assert.match(result.full, /GET \/vaults/);
  assert.throws(() => renderIndexes([...entries, entries[1]], (r) => pages.get(r), notes), /Duplicate/);
  assert.throws(() => renderIndexes(entries, () => undefined, notes), /Missing/);
});

test('agent notes reject known incorrect ABI, ordering, and undated yield claims', async () => {
  const { renderIndexes } = await import('./docs-lib.mjs');
  for (const note of [
    'Poll pendingRedeemRequest(account).',
    'Index 0 is `approve`, index 1 is `deposit`.',
    'For SuperStocks vaults, `reward_rate` is the primary yield today.',
  ]) assert.throws(() => renderIndexes([], () => undefined, note), /agent notes/i);
});

test('frontmatter rejects alternate engines without executing them in either path', async () => {
  const { renderIndexes, validatePages } = await import('./docs-lib.mjs');
  for (const engine of ['javascript', 'js']) {
    for (const mode of ['validate', 'render']) {
      delete globalThis.__operateFrontmatterProbe;
      const raw = `---${engine}\n({title: (globalThis.__operateFrontmatterProbe = 1, '${mode}')})\n---\nBody\n`;
      if (mode === 'validate') {
        const errors = await validatePages(new Map([['probe', raw]]), () => false);
        assert.equal(globalThis.__operateFrontmatterProbe, undefined);
        assert.match(errors.join('\n'), /frontmatter/i);
      } else {
        assert.throws(() => renderIndexes([{ route: 'probe', section: 'Test' }], () => raw, ''), /frontmatter/i);
        assert.equal(globalThis.__operateFrontmatterProbe, undefined);
      }
    }
  }
});

test('frontmatter rejects executable YAML tags in validator and generator', async () => {
  const { renderIndexes, validatePages } = await import('./docs-lib.mjs');
  const raw = '---\ntitle: !!js/function "function () { return 1; }"\n---\nBody\n';
  assert.match((await validatePages(new Map([['probe', raw]]), () => false)).join('\n'), /frontmatter/i);
  assert.throws(() => renderIndexes([{ route: 'probe', section: 'Test' }], () => raw, ''), /frontmatter/i);
});

test('MDX validation compiles content and detects local links, fragments, and invalid JSON', async () => {
  const { validatePages } = await import('./docs-lib.mjs');
  const valid = new Map([
    ['operate', '---\ntitle: Operate\n---\n## Overview\n\n[Access](/operate/access#roles)\n<Card href="/operate/access">Access</Card>\n'],
    ['operate/access', '---\ntitle: Access\n---\n## Roles\n\n[Home](/operate#overview)\n'],
  ]);
  assert.deepEqual(await validatePages(valid, () => false), []);
  const missing = new Map(valid).set('operate', '---\ntitle: Operate\n---\n## Overview\n\n[Missing](/absent)\n[Bad heading](/operate/access#missing)');
  assert.equal((await validatePages(missing, () => false)).length, 2);
  const malformed = new Map(valid).set('operate', '---\ntitle: Operate\n---\n<Warning>Unclosed');
  assert.match((await validatePages(malformed, () => false)).join('\n'), /MDX/);
  const invalidJSON = new Map(valid).set('operate', '---\ntitle: Operate\n---\n```json\n{"bad":}\n```');
  assert.match((await validatePages(invalidJSON, () => false)).join('\n'), /JSON/);
});
