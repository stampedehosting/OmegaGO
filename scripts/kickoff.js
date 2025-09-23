#!/usr/bin/env node
import { promises as fs } from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import fg from 'fast-glob';
import * as dotenv from 'dotenv';

function readCsvSync(filePath) {
  const content = fs.readFile(filePath, 'utf8');
  return content.then(text => parse(text, { columns: true, skip_empty_lines: true }));
}

function envPathForProject(projectId) {
  return path.join(process.cwd(), 'secrets', projectId, '.env');
}

async function fileExists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function loadEnvIfExists(projectId) {
  const envPath = envPathForProject(projectId);
  if (await fileExists(envPath)) {
    const envContent = await fs.readFile(envPath, 'utf8');
    const parsed = dotenv.parse(envContent);
    return { envPath, present: true, vars: Object.keys(parsed) };
  }
  return { envPath, present: false, vars: [] };
}

function pick(obj, keys) {
  return keys.reduce((acc, k) => { if (obj[k] !== undefined) acc[k] = obj[k]; return acc; }, {});
}

async function main() {
  const args = process.argv.slice(2);
  const isDryRun = args.includes('--dry-run') || !args.includes('--apply');

  const requiredFiles = [
    'PROJECTS_MANIFEST.csv',
    'PLAYWRIGHT_TESTS.csv',
    'WEBHOOKS.csv',
    'HTML_SITES.csv',
    'APPS.csv'
  ];

  const presentFiles = [];
  for (const f of requiredFiles) {
    const exists = await fileExists(path.join(process.cwd(), f));
    if (exists) presentFiles.push(f);
  }

  const missing = requiredFiles.filter(f => !presentFiles.includes(f));

  const manifest = (await readCsvSync(path.join(process.cwd(), 'PROJECTS_MANIFEST.csv')).catch(() => []));
  const byId = Object.fromEntries(manifest.map(r => [r.project_id, r]));

  const tests = (await readCsvSync(path.join(process.cwd(), 'PLAYWRIGHT_TESTS.csv')).catch(() => []));
  const testsById = Object.fromEntries(tests.map(r => [r.project_id, r]));

  const webhooks = (await readCsvSync(path.join(process.cwd(), 'WEBHOOKS.csv')).catch(() => []));
  const hooksById = Object.fromEntries(webhooks.map(r => [r.project_id, r]));

  const htmlSites = (await readCsvSync(path.join(process.cwd(), 'HTML_SITES.csv')).catch(() => []));
  const sitesById = Object.fromEntries(htmlSites.map(r => [r.project_id, r]));

  const apps = (await readCsvSync(path.join(process.cwd(), 'APPS.csv')).catch(() => []));
  const appsById = Object.fromEntries(apps.map(r => [r.project_id, r]));

  const projectIds = Object.keys(byId);

  const plans = [];
  for (const projectId of projectIds) {
    const meta = byId[projectId];
    const type = meta.type;
    const plan = { projectId, type, checks: [], actions: [] };

    // Env presence
    const envInfo = await loadEnvIfExists(projectId);
    plan.checks.push({ kind: 'env', ok: envInfo.present, details: envInfo });

    if (type === 'playwright_tests') {
      const t = testsById[projectId];
      plan.checks.push({ kind: 'tests_row', ok: !!t, details: pick(t || {}, ['url', 'browsers', 'devices']) });
      plan.actions.push('scaffold Playwright config and tests');
      plan.actions.push('wire CI to run on PR and nightly');
    }

    if (type === 'html_site') {
      const s = sitesById[projectId];
      plan.checks.push({ kind: 'html_row', ok: !!s, details: pick(s || {}, ['build_tool', 'i18n_locales']) });
      plan.actions.push('scaffold HTML site with chosen build tool');
      if (meta.deploy_target) plan.actions.push(`configure deploy: ${meta.deploy_target}`);
    }

    if (type === 'webhook') {
      const h = hooksById[projectId];
      plan.checks.push({ kind: 'webhook_row', ok: !!h, details: pick(h || {}, ['provider', 'endpoint_url']) });
      plan.actions.push('validate signing secret and subscribe events');
      plan.actions.push('provision DLQ and retries');
    }

    if (appsById[projectId]) {
      plan.actions.push('prepare app release pipeline');
    }

    plans.push(plan);
  }

  const summary = {
    missingFiles: missing,
    presentFiles,
    totalProjects: projectIds.length,
    plans,
  };

  if (isDryRun) {
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  // In apply mode, we would proceed to clone repos, write configs, and set up CI.
  // For now, we only create folders for secrets/content/assets that are missing.
  const toEnsure = [
    'secrets',
    'content',
    'assets',
    'imports'
  ];
  for (const dir of toEnsure) {
    await fs.mkdir(path.join(process.cwd(), dir), { recursive: true });
  }

  for (const projectId of projectIds) {
    await fs.mkdir(path.join(process.cwd(), 'secrets', projectId), { recursive: true });
    await fs.mkdir(path.join(process.cwd(), 'content', projectId), { recursive: true });
    await fs.mkdir(path.join(process.cwd(), 'assets', projectId), { recursive: true });
  }

  console.log('Apply step ensured base directories. Next steps: repo cloning and scaffolding.');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});