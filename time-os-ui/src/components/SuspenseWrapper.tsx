// SuspenseWrapper — consistent loading fallback for lazy-loaded components
import { Suspense, type ReactNode } from 'react';
import { SkeletonCardList } from './Skeleton';

interface SuspenseWrapperProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function SuspenseWrapper({ children, fallback }: SuspenseWrapperProps) {
  return <Suspense fallback={fallback || <DefaultFallback />}>{children}</Suspense>;
}

function DefaultFallback() {
  return (
    <div className="p-4">
      <SkeletonCardList count={3} />
    </div>
  );
}

// Page-level suspense with full-page loader
export function PageSuspense({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
}

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[var(--grey-light)]">Loading...</p>
      </div>
    </div>
  );
}
