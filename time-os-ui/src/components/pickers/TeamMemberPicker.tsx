// Searchable team member dropdown picker
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../auth/AuthContext';

interface TeamMember {
  id: string;
  name: string;
  role?: string;
  email?: string;
}

interface TeamMemberPickerProps {
  onSelect: (memberId: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function TeamMemberPicker({ onSelect, placeholder = 'Select team member...', disabled = false }: TeamMemberPickerProps) {
  const { token } = useAuth();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [filteredMembers, setFilteredMembers] = useState<TeamMember[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v2';

  // Fetch team members
  useEffect(() => {
    if (!token) return;

    const fetchMembers = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch(`${apiBase}/team`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error('Failed to fetch team members');
        }

        const data = await response.json();
        // Handle both direct array and nested members array
        const membersList = Array.isArray(data) ? data : data.members || [];
        setMembers(membersList);
        setFilteredMembers(membersList);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load team members');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchMembers();
  }, [token, apiBase]);

  // Filter members based on search term
  useEffect(() => {
    const term = searchTerm.toLowerCase();
    const filtered = members.filter(
      (member) =>
        member.name.toLowerCase().includes(term) ||
        member.email?.toLowerCase().includes(term) ||
        member.id.toLowerCase().includes(term)
    );
    setFilteredMembers(filtered);
  }, [searchTerm, members]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleSelect = (memberId: string) => {
    onSelect(memberId);
    setSearchTerm('');
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setIsOpen(true)}
          placeholder={placeholder}
          disabled={disabled || loading}
          className="w-full px-4 py-2 rounded-lg bg-[var(--grey-dim)] text-[var(--white)] placeholder-[var(--grey)] border border-[var(--grey)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 outline-none transition-colors disabled:opacity-50"
        />
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="animate-spin h-4 w-4 border-2 border-[var(--accent)] border-t-transparent rounded-full" />
          </div>
        )}
      </div>

      {error && (
        <div className="mt-2 text-sm text-[var(--danger)]">
          {error}
        </div>
      )}

      {isOpen && !disabled && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--grey-dim)] border border-[var(--grey)] rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
          {filteredMembers.length === 0 ? (
            <div className="px-4 py-3 text-center text-[var(--grey)]">
              {loading ? 'Loading...' : 'No team members found'}
            </div>
          ) : (
            filteredMembers.map((member) => (
              <button
                key={member.id}
                onClick={() => handleSelect(member.id)}
                className="w-full text-left px-4 py-2 hover:bg-[var(--grey)] transition-colors border-b border-[var(--grey)]/50 last:border-b-0"
              >
                <div className="font-medium text-[var(--white)]">{member.name}</div>
                {member.role && (
                  <div className="text-sm text-[var(--grey)]">{member.role}</div>
                )}
                {member.email && (
                  <div className="text-xs text-[var(--grey)]">{member.email}</div>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
