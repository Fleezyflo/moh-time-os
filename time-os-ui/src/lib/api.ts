// API client for Control Room endpoints
// Connects to FastAPI backend at /api/control-room/*

const API_BASE = 'http://localhost:8420/api/control-room';

export async function fetchProposals(limit = 7, status = 'open') {
  const res = await fetch(`${API_BASE}/proposals?limit=${limit}&status=${status}`);
  if (!res.ok) throw new Error(`Failed to fetch proposals: ${res.status}`);
  return res.json();
}

export async function fetchIssues(limit = 5) {
  const res = await fetch(`${API_BASE}/issues?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch issues: ${res.status}`);
  return res.json();
}

export async function fetchWatchers(hours = 24) {
  const res = await fetch(`${API_BASE}/watchers?hours=${hours}`);
  if (!res.ok) throw new Error(`Failed to fetch watchers: ${res.status}`);
  return res.json();
}

export async function fetchFixData() {
  const res = await fetch(`${API_BASE}/fix-data`);
  if (!res.ok) throw new Error(`Failed to fetch fix-data: ${res.status}`);
  return res.json();
}

export async function fetchCouplings(anchorType?: string, anchorId?: string) {
  let url = `${API_BASE}/couplings`;
  if (anchorType && anchorId) {
    url += `?anchor_type=${anchorType}&anchor_id=${anchorId}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch couplings: ${res.status}`);
  return res.json();
}

export async function fetchAllCouplings() {
  const res = await fetch(`${API_BASE}/couplings`);
  if (!res.ok) throw new Error(`Failed to fetch couplings: ${res.status}`);
  return res.json();
}

export async function fetchClients() {
  const res = await fetch(`${API_BASE}/clients`);
  if (!res.ok) throw new Error(`Failed to fetch clients: ${res.status}`);
  return res.json();
}

export async function fetchTeam() {
  const res = await fetch(`${API_BASE}/team`);
  if (!res.ok) throw new Error(`Failed to fetch team: ${res.status}`);
  return res.json();
}

export async function fetchEvidence(entityType: string, entityId: string) {
  const res = await fetch(`${API_BASE}/evidence/${entityType}/${entityId}`);
  if (!res.ok) throw new Error(`Failed to fetch evidence: ${res.status}`);
  return res.json();
}
