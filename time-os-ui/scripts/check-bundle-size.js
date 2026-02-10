#!/usr/bin/env node
/**
 * Bundle size budget check.
 *
 * Enforces maximum sizes for production bundles.
 * Fails CI if any bundle exceeds its budget.
 */

import { readdirSync, statSync } from 'fs';
import { join } from 'path';

// Budget limits in KB
// Note: These are realistic budgets for a production SPA with React + Router + Zustand
const BUDGETS = {
  js: 500,      // Main JS bundle (includes vendor in Vite)
  css: 100,     // Main CSS (Tailwind)
  total: 1000,  // Total assets
};

const distDir = join(process.cwd(), 'dist', 'assets');

function getFileSizeKB(filePath) {
  return statSync(filePath).size / 1024;
}

function checkBudgets() {
  let totalSize = 0;
  let jsSize = 0;
  let cssSize = 0;
  let violations = [];

  try {
    const files = readdirSync(distDir);

    for (const file of files) {
      const filePath = join(distDir, file);
      const sizeKB = getFileSizeKB(filePath);
      totalSize += sizeKB;

      if (file.endsWith('.js')) {
        jsSize += sizeKB;
        console.log(`  JS: ${file}: ${sizeKB.toFixed(1)}KB`);
      } else if (file.endsWith('.css')) {
        cssSize += sizeKB;
        console.log(`  CSS: ${file}: ${sizeKB.toFixed(1)}KB`);
      }
    }

    // Check budgets
    if (jsSize > BUDGETS.js) {
      violations.push(`JS total: ${jsSize.toFixed(1)}KB exceeds budget of ${BUDGETS.js}KB`);
    } else {
      console.log(`✓ JS total: ${jsSize.toFixed(1)}KB (budget: ${BUDGETS.js}KB)`);
    }

    if (cssSize > BUDGETS.css) {
      violations.push(`CSS total: ${cssSize.toFixed(1)}KB exceeds budget of ${BUDGETS.css}KB`);
    } else {
      console.log(`✓ CSS total: ${cssSize.toFixed(1)}KB (budget: ${BUDGETS.css}KB)`);
    }

    if (totalSize > BUDGETS.total) {
      violations.push(`Total: ${totalSize.toFixed(1)}KB exceeds budget of ${BUDGETS.total}KB`);
    } else {
      console.log(`✓ Total: ${totalSize.toFixed(1)}KB (budget: ${BUDGETS.total}KB)`);
    }

    if (violations.length > 0) {
      console.error('\n❌ Bundle budget violations:');
      violations.forEach(v => console.error(`   ${v}`));
      process.exit(1);
    }

    console.log('\n✅ All bundles within budget');
  } catch (error) {
    if (error.code === 'ENOENT') {
      console.error('❌ dist/assets not found. Run `pnpm build` first.');
      process.exit(1);
    }
    throw error;
  }
}

checkBudgets();
