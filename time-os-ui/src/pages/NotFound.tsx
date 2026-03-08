import { Link } from '@tanstack/react-router';

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <h1 className="text-6xl font-bold text-[var(--white)] mb-4">404</h1>
      <p className="text-xl text-[var(--grey-light)] mb-8">Page not found</p>
      <Link
        to="/"
        className="px-6 py-3 bg-[var(--grey)] hover:bg-[var(--grey-light)] text-white rounded-lg transition-colors min-h-[44px] inline-flex items-center"
      >
        Back to Inbox
      </Link>
    </div>
  );
}
