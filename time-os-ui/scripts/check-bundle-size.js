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
const BUDGETS = {
  'index.js': 250,      // Main bundle
  'vendor.js': 500,     // Vendor/node_modules
  'index.css': 50,      // Main CSS
  total: 800,           // Total assets
};

const distDir = join(process.cwd(), 'dist', 'assets');

function getFileSizeKB(filePath) {
  return statSync(filePath).size / 1024;
}

function checkBudgets() {
  let totalSize = 0;
  let violations = [];

  try {
    const files = readdirSync(distDir);

    for (const file of files) {
      const filePath = join(distDir, file);
      const sizeKB = getFileSizeKB(filePath);
      totalSize += sizeKB;

      // Check individual file budgets
      for (const [pattern, budget] of Object.entries(BUDGETS)) {
        if (pattern === 'total') continue;
        if (file.includes(pattern.replace('.js', '').replace('.css', ''))) {
          if (sizeKB > budget) {
            violations.push(`${file}: ${sizeKB.toFixed(1)}KB exceeds budget of ${budget}KB`);
          } else {
            console.log(`✓ ${file}: ${sizeKB.toFixed(1)}KB (budget: ${budget}KB)`);
          }
        }
      }
    }

    // Check total budget
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
