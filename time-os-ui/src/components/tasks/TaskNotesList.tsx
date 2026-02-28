// TaskNotesList — Displays task notes as a timeline
interface TaskNotesListProps {
  notesJson: string | null;
}

interface TaskNote {
  text: string;
  added_at?: string;
  added_by?: string;
}

function parseNotes(notesJson: string | null): TaskNote[] {
  if (!notesJson) return [];
  try {
    const parsed = JSON.parse(notesJson);
    if (Array.isArray(parsed)) return parsed;
    if (typeof parsed === 'string') return [{ text: parsed }];
    return [];
  } catch {
    // Plain text note
    if (typeof notesJson === 'string' && notesJson.trim()) {
      return [{ text: notesJson }];
    }
    return [];
  }
}

export function TaskNotesList({ notesJson }: TaskNotesListProps) {
  const notes = parseNotes(notesJson);

  if (notes.length === 0) {
    return <p className="text-xs text-[var(--grey-muted)] italic">No notes yet.</p>;
  }

  return (
    <div className="space-y-2">
      {notes.map((note, i) => (
        <div
          key={`note-${i}`}
          className="p-2 rounded bg-[var(--grey)]/50 text-sm text-[var(--grey-light)]"
        >
          <p>{note.text}</p>
          {(note.added_at || note.added_by) && (
            <p className="text-xs text-[var(--grey-muted)] mt-1">
              {note.added_by && <span>{note.added_by}</span>}
              {note.added_by && note.added_at && <span> &middot; </span>}
              {note.added_at && (
                <span>
                  {new Date(note.added_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              )}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
