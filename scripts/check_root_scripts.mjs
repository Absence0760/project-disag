#!/usr/bin/env node
// Guard for the root package.json scripts block — validates it against the
// estate format documented in CLAUDE.md ("Root package.json scripts").
// Adapted from project-running's scripts/check_root_scripts.mjs.
// Stdlib only; run with `pnpm test:scripts` or `node scripts/check_root_scripts.mjs`.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(fs.readFileSync(path.join(rootDir, 'package.json'), 'utf8'));
const scripts = pkg.scripts ?? {};
const errors = [];

const DIVIDER_RE = /^\/\/-- (.+) --$/;

// Verb prefixes canonized by the estate format (see CLAUDE.md examples).
const KNOWN_VERBS = new Set([
  'setup', 'dev', 'start', 'build', 'preview', 'check', 'format', 'e2e',
  'tf', 'deploy', 'test', 'gen', 'up', 'down', 'status', 'logs',
]);

// pnpm subcommands that are commands, not workspace scripts.
const RESERVED_PNPM_VERBS = new Set([
  'install', 'add', 'remove', 'update', 'exec', 'dlx',
  'run', 'test', 'start', 'build', 'publish', 'pack', 'audit',
  'list', 'ls', 'why', 'outdated', 'config', 'store', 'recursive',
  'rebuild', 'prune', 'link', 'unlink', 'import', 'fetch',
]);

// Workspace name → dir, from pnpm-workspace.yaml `packages:` entries.
const workspaceDirs = new Map();
const wsYaml = path.join(rootDir, 'pnpm-workspace.yaml');
if (fs.existsSync(wsYaml)) {
  const packagesBlock = fs.readFileSync(wsYaml, 'utf8')
    .split(/\r?\n/)
    .filter((line) => /^\s*-\s+/.test(line))
    .map((line) => line.replace(/^\s*-\s+/, '').replace(/['"]/g, '').trim());
  for (const entry of packagesBlock) {
    const dirs = entry.endsWith('/*')
      ? fs.readdirSync(path.join(rootDir, entry.slice(0, -2)), { withFileTypes: true })
          .filter((d) => d.isDirectory())
          .map((d) => path.join(entry.slice(0, -2), d.name))
      : [entry];
    for (const dir of dirs) {
      const childPath = path.join(rootDir, dir, 'package.json');
      if (!fs.existsSync(childPath)) continue;
      const child = JSON.parse(fs.readFileSync(childPath, 'utf8'));
      if (child.name) workspaceDirs.set(child.name, { dir, scripts: child.scripts ?? {} });
    }
  }
}

const childPkgCache = new Map();
function loadChildPkg(dir) {
  if (childPkgCache.has(dir)) return childPkgCache.get(dir);
  const childPath = path.join(rootDir, dir, 'package.json');
  const json = fs.existsSync(childPath) ? JSON.parse(fs.readFileSync(childPath, 'utf8')) : null;
  childPkgCache.set(dir, json);
  return json;
}

function checkWorkspaceScript(name, owner, ownerScripts, target) {
  if (!target || RESERVED_PNPM_VERBS.has(target)) return;
  if (!(target in ownerScripts)) {
    errors.push(`${name}: ${owner} has no "${target}" script`);
  }
}

let seenDivider = false;
let scriptCount = 0;

for (const [name, cmd] of Object.entries(scripts)) {
  const divider = name.match(DIVIDER_RE);
  if (divider || name.startsWith('//')) {
    if (!divider) {
      errors.push(`"${name}": malformed divider key — expected "//-- <group> --"`);
    } else if (typeof cmd !== 'string' || cmd.trim() === '') {
      errors.push(`"${name}": divider has no description — the value must carry load-bearing facts`);
    }
    seenDivider = true;
    continue;
  }
  scriptCount++;

  // Rule: every script belongs to a `//-- <group> --` divider.
  if (!seenDivider) {
    errors.push(`${name}: script appears before the first "//-- <group> --" divider`);
  }

  // Rule: verb-first, colon-namespaced names.
  const verb = name.split(':')[0];
  if (!KNOWN_VERBS.has(verb)) {
    errors.push(`${name}: unknown verb prefix "${verb}" — expected one of: ${[...KNOWN_VERBS].join(', ')}`);
  }

  // Rule: `pnpm --filter <workspace> [run] <script>` targets must exist.
  for (const m of cmd.matchAll(/pnpm\s+--filter[= ]\s*(\S+)\s+(?:run\s+)?(\S+)/g)) {
    const [, wsName, target] = m;
    const ws = workspaceDirs.get(wsName);
    if (!ws) {
      errors.push(`${name}: unknown workspace "${wsName}" (not found via pnpm-workspace.yaml)`);
      continue;
    }
    checkWorkspaceScript(name, `${ws.dir}/package.json`, ws.scripts, target);
  }

  // Rule: `pnpm -C <dir> [run] <script>` targets must exist.
  for (const m of cmd.matchAll(/pnpm\s+-C\s+(\S+)\s+(?:run\s+)?(\S+)/g)) {
    const [, dir, target] = m;
    const child = loadChildPkg(dir);
    if (!child) {
      errors.push(`${name}: missing ${dir}/package.json`);
      continue;
    }
    checkWorkspaceScript(name, `${dir}/package.json`, child.scripts ?? {}, target);
  }

  // Rule: `cd <dir>` targets must exist.
  for (const m of cmd.matchAll(/(?:^|&&\s*)cd\s+([A-Za-z0-9_./-]+)/g)) {
    if (!fs.existsSync(path.join(rootDir, m[1]))) {
      errors.push(`${name}: missing directory ${m[1]}`);
    }
  }

  // Rule: referenced repo-relative files must exist. Matches bare tokens
  // like scripts/export-tf-vars.sh — shell-expansion tokens ($, ://) and
  // runtime-generated paths (.venv/bin/*, no extension) never match.
  for (const m of cmd.matchAll(
    /(?:^|[\s"'=])((?:[A-Za-z0-9_.-]+\/)+[A-Za-z0-9_.-]+\.(?:sh|py|mjs|cjs|js|ts|txt|ya?ml|json))(?=$|[\s"'&;)])/g,
  )) {
    const file = m[1];
    if (file.includes('..')) continue; // relative to a `cd`, not the root
    if (!fs.existsSync(path.join(rootDir, file))) {
      errors.push(`${name}: missing file ${file}`);
    }
  }
}

if (errors.length) {
  console.error(`Root scripts validation failed (${errors.length} issue${errors.length === 1 ? '' : 's'}):`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`Root scripts validation passed (${scriptCount} scripts).`);
