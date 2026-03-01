// ProjectProposalForm — inline form for proposing new projects (Phase 12)
// This is an alternative standalone form; EnrollmentActionBar has an inline version too.
import { useState } from 'react';

interface ProjectProposalFormProps {
  onSubmit: (name: string, clientId?: string, type?: string) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ProjectProposalForm({
  onSubmit,
  onCancel,
  loading = false,
}: ProjectProposalFormProps) {
  const [name, setName] = useState('');
  const [clientId, setClientId] = useState('');
  const [type, setType] = useState('retainer');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit(name.trim(), clientId.trim() || undefined, type);
  };

  return (
    <form onSubmit={handleSubmit} className="card p-4 space-y-4">
      <h3 className="font-medium text-[var(--white)]">Propose New Project</h3>

      <div className="space-y-3">
        <div>
          <label htmlFor="project-name" className="block text-xs text-[var(--grey-light)] mb-1">
            Project Name *
          </label>
          <input
            id="project-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Website Redesign"
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey-dim)] border border-[var(--grey)] text-[var(--white)] placeholder:text-[var(--grey-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            required
            autoFocus
          />
        </div>

        <div>
          <label htmlFor="project-client" className="block text-xs text-[var(--grey-light)] mb-1">
            Client ID (optional)
          </label>
          <input
            id="project-client"
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Client identifier"
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey-dim)] border border-[var(--grey)] text-[var(--white)] placeholder:text-[var(--grey-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
        </div>

        <div>
          <label htmlFor="project-type" className="block text-xs text-[var(--grey-light)] mb-1">
            Type
          </label>
          <select
            id="project-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey-dim)] border border-[var(--grey)] text-[var(--white)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          >
            <option value="retainer">Retainer</option>
            <option value="project">Project</option>
          </select>
        </div>
      </div>

      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded bg-[var(--grey)] hover:bg-[var(--grey-mid)] text-[var(--grey-light)] transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || loading}
          className="px-4 py-2 text-sm font-medium rounded bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-white transition-colors disabled:opacity-50"
        >
          {loading ? 'Creating...' : 'Propose Project'}
        </button>
      </div>
    </form>
  );
}

export default ProjectProposalForm;
