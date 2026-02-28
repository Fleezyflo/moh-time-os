// TaskDetail page — Full task view with edit, notes, delegation, escalation
import { useState } from 'react';
import { useParams, useNavigate } from '@tanstack/react-router';
import { SkeletonCardList, ErrorState, useToast } from '../components';
import { PageLayout } from '../components/layout/PageLayout';
import { TaskActions } from '../components/tasks/TaskActions';
import { DelegationPanel } from '../components/tasks/DelegationPanel';
import { TaskNotesList } from '../components/tasks/TaskNotesList';
import { ApprovalDialog } from '../components/tasks/ApprovalDialog';
import { useTaskDetail } from '../lib/hooks';
import * as api from '../lib/api';
import type { TaskUpdatePayload } from '../lib/api';

const STATUS_OPTIONS = ['pending', 'in_progress', 'blocked', 'completed', 'cancelled', 'archived'];

function priorityLabel(score: number): string {
  if (score >= 80) return 'Urgent';
  if (score >= 60) return 'High';
  if (score >= 30) return 'Medium';
  return 'Low';
}

function priorityColor(score: number): string {
  if (score >= 80) return 'var(--danger)';
  if (score >= 60) return 'var(--warning)';
  if (score >= 30) return 'var(--accent)';
  return 'var(--grey-light)';
}

function statusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'var(--grey-light)',
    in_progress: 'var(--accent)',
    blocked: 'var(--danger)',
    completed: 'var(--success)',
    done: 'var(--success)',
    cancelled: 'var(--grey-muted)',
    archived: 'var(--grey-muted)',
  };
  return colors[status] || 'var(--grey-muted)';
}

export default function TaskDetail() {
  const { taskId } = useParams({ strict: false });
  const navigate = useNavigate();
  const toast = useToast();

  const { data: task, loading, error, refetch } = useTaskDetail(taskId || '');

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editFields, setEditFields] = useState<TaskUpdatePayload>({});
  const [approvalInfo, setApprovalInfo] = useState<{
    reason?: string;
    decision_id?: string;
  } | null>(null);

  if (!taskId) {
    return (
      <PageLayout title="Task Not Found">
        <p className="text-[var(--grey-light)]">No task ID provided.</p>
      </PageLayout>
    );
  }

  if (loading) return <SkeletonCardList count={3} />;
  if (error) return <ErrorState error={error} onRetry={refetch} hasData={false} />;
  if (!task) {
    return (
      <PageLayout title="Task Not Found">
        <p className="text-[var(--grey-light)]">Task {taskId} could not be found.</p>
      </PageLayout>
    );
  }

  const startEdit = () => {
    setEditFields({
      title: task.title,
      description: task.description || '',
      status: task.status,
      priority: task.priority,
      assignee: task.assignee || '',
      project: task.project || '',
      due_date: task.due_date || '',
      tags: task.tags || '',
    });
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditFields({});
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      // Only send fields that changed
      const changes: TaskUpdatePayload = {};
      if (editFields.title !== task.title) changes.title = editFields.title;
      if (editFields.description !== (task.description || ''))
        changes.description = editFields.description;
      if (editFields.status !== task.status) changes.status = editFields.status;
      if (editFields.priority !== task.priority) changes.priority = editFields.priority;
      if (editFields.assignee !== (task.assignee || '')) changes.assignee = editFields.assignee;
      if (editFields.project !== (task.project || '')) changes.project = editFields.project;
      if (editFields.due_date !== (task.due_date || '')) changes.due_date = editFields.due_date;
      if (editFields.tags !== (task.tags || '')) changes.tags = editFields.tags;

      if (Object.keys(changes).length === 0) {
        toast.success('No changes to save');
        setEditing(false);
        return;
      }

      const result = await api.updateTask(taskId, changes);
      if (result.requires_approval) {
        setApprovalInfo({
          reason: result.reason,
          decision_id: result.decision_id,
        });
      } else if (result.success) {
        toast.success('Task updated');
        setEditing(false);
        refetch();
      } else {
        toast.error(result.error || 'Update failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageLayout
      title={editing ? 'Edit Task' : task.title}
      subtitle={
        editing
          ? undefined
          : `${task.status} · Priority ${task.priority} · ${task.assignee || 'Unassigned'}`
      }
      actions={
        <div className="flex gap-2">
          <button
            onClick={() => navigate({ to: '/tasks' })}
            className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] transition-colors"
          >
            Back to Tasks
          </button>
          {!editing && (
            <button
              onClick={startEdit}
              className="px-3 py-1.5 text-xs font-medium rounded bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-white transition-colors"
            >
              Edit
            </button>
          )}
        </div>
      }
    >
      {approvalInfo && (
        <ApprovalDialog
          reason={approvalInfo.reason}
          decisionId={approvalInfo.decision_id}
          onClose={() => setApprovalInfo(null)}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {editing ? (
            <EditForm
              fields={editFields}
              onChange={setEditFields}
              onSave={saveEdit}
              onCancel={cancelEdit}
              saving={saving}
            />
          ) : (
            <>
              {/* Status + Priority bar */}
              <div className="flex items-center gap-4 flex-wrap">
                <span
                  className="px-2 py-1 rounded text-xs font-medium"
                  style={{
                    backgroundColor: statusColor(task.status),
                    color: 'var(--white)',
                  }}
                >
                  {task.status}
                </span>
                <span
                  className="text-sm font-medium"
                  style={{ color: priorityColor(task.priority) }}
                >
                  {priorityLabel(task.priority)} ({task.priority})
                </span>
                {task.urgency && task.urgency !== 'normal' && (
                  <span className="text-xs text-[var(--warning)]">{task.urgency}</span>
                )}
                {task.due_date && (
                  <span className="text-sm text-[var(--grey-light)]">
                    Due:{' '}
                    {new Date(task.due_date).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </span>
                )}
              </div>

              {/* Description */}
              {task.description && (
                <div>
                  <h3 className="text-xs font-medium text-[var(--grey-muted)] uppercase tracking-wide mb-2">
                    Description
                  </h3>
                  <p className="text-sm text-[var(--grey-light)]">{task.description}</p>
                </div>
              )}

              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-3">
                <MetadataItem label="Assignee" value={task.assignee || 'Unassigned'} />
                <MetadataItem label="Project" value={task.project || 'None'} />
                <MetadataItem label="Source" value={task.source || 'Unknown'} />
                <MetadataItem label="Tags" value={task.tags || 'None'} />
                <MetadataItem
                  label="Created"
                  value={new Date(task.created_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                />
                <MetadataItem
                  label="Updated"
                  value={new Date(task.updated_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                />
              </div>

              {/* Notes */}
              <div>
                <h3 className="text-xs font-medium text-[var(--grey-muted)] uppercase tracking-wide mb-2">
                  Notes
                </h3>
                <TaskNotesList notesJson={task.notes || null} />
              </div>

              {/* Actions */}
              <div>
                <h3 className="text-xs font-medium text-[var(--grey-muted)] uppercase tracking-wide mb-2">
                  Actions
                </h3>
                <TaskActions
                  task={task}
                  onAction={refetch}
                  onApprovalRequired={setApprovalInfo}
                  toast={toast}
                />
              </div>
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <DelegationPanel task={task} />
        </div>
      </div>
    </PageLayout>
  );
}

// -- Subcomponents --

function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-[var(--grey-muted)]">{label}</span>
      <p className="text-sm text-[var(--white)]">{value}</p>
    </div>
  );
}

function EditForm({
  fields,
  onChange,
  onSave,
  onCancel,
  saving,
}: {
  fields: api.TaskUpdatePayload;
  onChange: (f: api.TaskUpdatePayload) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const update = (key: keyof api.TaskUpdatePayload, value: string | number) => {
    onChange({ ...fields, [key]: value });
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs text-[var(--grey-muted)] mb-1">Title</label>
        <input
          type="text"
          value={fields.title || ''}
          onChange={(e) => update('title', e.target.value)}
          className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
        />
      </div>
      <div>
        <label className="block text-xs text-[var(--grey-muted)] mb-1">Description</label>
        <textarea
          value={fields.description || ''}
          onChange={(e) => update('description', e.target.value)}
          rows={3}
          className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)] resize-none"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-[var(--grey-muted)] mb-1">Status</label>
          <select
            value={fields.status || ''}
            onChange={(e) => update('status', e.target.value)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-[var(--grey-muted)] mb-1">Priority (0-100)</label>
          <input
            type="number"
            min={0}
            max={100}
            value={fields.priority ?? 50}
            onChange={(e) => update('priority', parseInt(e.target.value, 10) || 0)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--grey-muted)] mb-1">Assignee</label>
          <input
            type="text"
            value={fields.assignee || ''}
            onChange={(e) => update('assignee', e.target.value)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--grey-muted)] mb-1">Project</label>
          <input
            type="text"
            value={fields.project || ''}
            onChange={(e) => update('project', e.target.value)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--grey-muted)] mb-1">Due Date</label>
          <input
            type="date"
            value={fields.due_date || ''}
            onChange={(e) => update('due_date', e.target.value)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--grey-muted)] mb-1">Tags</label>
          <input
            type="text"
            value={fields.tags || ''}
            onChange={(e) => update('tags', e.target.value)}
            className="w-full px-3 py-2 text-sm rounded bg-[var(--grey)] border border-[var(--border)] text-[var(--white)]"
          />
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          disabled={saving}
          className="px-4 py-2 rounded text-sm font-medium bg-[var(--grey)] hover:bg-[var(--grey-light)] text-[var(--white)] transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className="px-4 py-2 rounded text-sm font-medium bg-[var(--accent)] hover:bg-[var(--accent)]/80 text-white transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
