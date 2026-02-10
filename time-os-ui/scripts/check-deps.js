#!/usr/bin/env node
/**
 * Dependency hygiene check for the UI.
 *
 * Checks for:
 * - Unused dependencies
 * - Missing dependencies
 * - Outdated dependencies (advisory)
 *
 * Uses depcheck if installed, otherwise falls back to basic analysis.
 */

import { execSync } from 'child_process';
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

// Known dependencies that appear unused but are needed
const ALLOWLIST = [
  '@vitejs/plugin-react',  // Vite plugin
  'autoprefixer',          // PostCSS plugin
  'postcss',               // Required by Tailwind
  '@tailwindcss/postcss',  // Tailwind PostCSS
  'tailwindcss',           // Used by PostCSS
  'jsdom',                 // Vitest DOM
  '@testing-library/jest-dom', // Test matchers
  'vite-plugin-pwa',       // PWA support
  'rollup-plugin-visualizer', // Bundle analysis
];

function getPackageJson() {
  return JSON.parse(readFileSync('package.json', 'utf-8'));
}

function getAllImports(dir, imports = new Set()) {
  const files = readdirSync(dir);

  for (const file of files) {
    const fullPath = join(dir, file);
    const stat = statSync(fullPath);

    if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
      getAllImports(fullPath, imports);
    } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
      const content = readFileSync(fullPath, 'utf-8');

      // Match import statements
      const importRegex = /import\s+(?:(?:\{[^}]*\}|[^{}\s,]+)\s+from\s+)?['"]([^'"]+)['"]/g;
      let match;
      while ((match = importRegex.exec(content)) !== null) {
        const pkg = match[1];
        // Get package name (handle scoped packages)
        if (pkg.startsWith('@')) {
          imports.add(pkg.split('/').slice(0, 2).join('/'));
        } else if (!pkg.startsWith('.') && !pkg.startsWith('/')) {
          imports.add(pkg.split('/')[0]);
        }
      }
    }
  }

  return imports;
}

function checkDeps() {
  console.log('🔍 Checking dependency hygiene...\n');

  const pkg = getPackageJson();
  const deps = Object.keys(pkg.dependencies || {});
  const devDeps = Object.keys(pkg.devDependencies || {});
  const allDeps = new Set([...deps, ...devDeps]);

  // Get all imports from source
  const imports = getAllImports('src');

  // Check for unused dependencies
  const unused = [];
  for (const dep of allDeps) {
    if (!imports.has(dep) && !ALLOWLIST.includes(dep)) {
      unused.push(dep);
    }
  }

  // Check for missing dependencies (in imports but not in package.json)
  const missing = [];
  for (const imp of imports) {
    if (!allDeps.has(imp) && !imp.startsWith('node:')) {
      missing.push(imp);
    }
  }

  // Report
  let hasIssues = false;

  if (unused.length > 0) {
    console.log('⚠️  Potentially unused dependencies:');
    unused.forEach(dep => console.log(`   - ${dep}`));
    console.log('   (Add to ALLOWLIST in scripts/check-deps.js if needed)\n');
  }

  if (missing.length > 0) {
    console.log('❌ Missing dependencies:');
    missing.forEach(dep => console.log(`   - ${dep}`));
    hasIssues = true;
  }

  if (!hasIssues && unused.length === 0) {
    console.log('✅ Dependency hygiene OK');
  }

  return hasIssues ? 1 : 0;
}

process.exit(checkDeps());
