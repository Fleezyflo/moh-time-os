/**
 * PageLayout — Consistent page wrapper for all pages.
 *
 * Provides: header area (title + optional actions slot), consistent max-width,
 * padding, and spacing. Every page in the product uses this component.
 */

import type { ReactNode } from 'react';

interface PageLayoutProps {
  /** Page title displayed in the header */
  title: string;
  /** Optional subtitle or description below the title */
  subtitle?: string;
  /** Optional actions slot rendered to the right of the title */
  actions?: ReactNode;
  /** Page content */
  children: ReactNode;
}

export function PageLayout({ title, subtitle, actions, children }: PageLayoutProps) {
  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: 'var(--white)', fontFamily: 'var(--font-primary)' }}
          >
            {title}
          </h1>
          {subtitle && (
            <p className="mt-1 text-sm" style={{ color: 'var(--grey-light)' }}>
              {subtitle}
            </p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>

      {/* Content */}
      {children}
    </div>
  );
}
