"""
Client Linker - Link projects to clients.

Handles:
- Manual project-client linking
- Auto-linking by name matching
- Project lookup by client
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.state_store import get_store


class ClientLinker:
    """
    Manages project-client relationships.
    
    Invariant: Every project maps to zero or one client.
    """
    
    def __init__(self, store=None):
        self.store = store or get_store()
    
    def link_project_to_client(self, project_id: str, client_id: str) -> Tuple[bool, str]:
        """
        Link a project to a client.
        
        Args:
            project_id: Project ID
            client_id: Client ID
            
        Returns:
            (success, message)
        """
        # Verify project exists
        project = self.store.get('projects', project_id)
        if not project:
            return False, f"Project {project_id} not found"
        
        # Verify client exists
        client = self.store.get('clients', client_id)
        if not client:
            return False, f"Client {client_id} not found"
        
        # Check if already linked
        existing = self.store.query("""
            SELECT * FROM client_projects
            WHERE project_id = ?
        """, [project_id])
        
        if existing:
            if existing[0]['client_id'] == client_id:
                return True, "Already linked"
            else:
                # Update link
                self.store.query("""
                    UPDATE client_projects 
                    SET client_id = ?, linked_at = ?
                    WHERE project_id = ?
                """, [client_id, datetime.now().isoformat(), project_id])
                return True, f"Updated link from {existing[0]['client_id']} to {client_id}"
        
        # Create new link
        now = datetime.now().isoformat()
        self.store.insert('client_projects', {
            'client_id': client_id,
            'project_id': project_id,
            'linked_at': now
        })
        
        return True, f"Linked project to client {client.get('name', client_id)}"
    
    def unlink_project(self, project_id: str) -> Tuple[bool, str]:
        """Remove project-client link."""
        self.store.query(
            "DELETE FROM client_projects WHERE project_id = ?",
            [project_id]
        )
        return True, "Project unlinked"
    
    def auto_link_by_name(self) -> Dict:
        """
        Automatically link projects to clients by name matching.
        
        Matches project names that start with client names.
        e.g., "Aswaaq: Feb Campaign" → client "Aswaaq"
        
        Returns:
            Stats about linking
        """
        results = {
            'linked': 0,
            'already_linked': 0,
            'no_match': 0,
            'errors': []
        }
        
        # Get all projects
        projects = self.store.query("SELECT id, name FROM projects")
        
        # Get all clients for matching
        clients = self.store.query("SELECT id, name FROM clients")
        client_names = {c['name'].lower(): c['id'] for c in clients}
        
        for project in projects:
            project_name = project.get('name', '')
            
            # Check if already linked
            existing = self.store.query(
                "SELECT * FROM client_projects WHERE project_id = ?",
                [project['id']]
            )
            if existing:
                results['already_linked'] += 1
                continue
            
            # Try to match client name
            matched_client = None
            project_lower = project_name.lower()
            
            # Strategy 1: Prefix match (e.g., "Aswaaq:" or "Aswaaq -")
            for client_name, client_id in client_names.items():
                if project_lower.startswith(client_name + ':') or \
                   project_lower.startswith(client_name + ' -') or \
                   project_lower.startswith(client_name + ' |'):
                    matched_client = client_id
                    break
            
            # Strategy 2: Contains client name (looser match)
            if not matched_client:
                for client_name, client_id in client_names.items():
                    if len(client_name) >= 4 and client_name in project_lower:
                        matched_client = client_id
                        break
            
            if matched_client:
                success, msg = self.link_project_to_client(project['id'], matched_client)
                if success:
                    results['linked'] += 1
                else:
                    results['errors'].append(msg)
            else:
                results['no_match'] += 1
        
        return results
    
    def get_client_projects(self, client_id: str) -> List[Dict]:
        """Get all projects linked to a client."""
        projects = self.store.query("""
            SELECT p.*, cp.linked_at
            FROM projects p
            JOIN client_projects cp ON p.id = cp.project_id
            WHERE cp.client_id = ?
            ORDER BY cp.linked_at DESC
        """, [client_id])
        
        return projects
    
    def get_project_client(self, project_id: str) -> Optional[Dict]:
        """Get the client linked to a project."""
        result = self.store.query("""
            SELECT c.*
            FROM clients c
            JOIN client_projects cp ON c.id = cp.client_id
            WHERE cp.project_id = ?
        """, [project_id])
        
        return result[0] if result else None
    
    def get_unlinked_projects(self) -> List[Dict]:
        """Get projects not linked to any client."""
        return self.store.query("""
            SELECT p.* FROM projects p
            WHERE p.id NOT IN (SELECT project_id FROM client_projects)
        """)
    
    def get_linking_stats(self) -> Dict:
        """Get statistics about project-client linking."""
        total_projects = self.store.query(
            "SELECT COUNT(*) as c FROM projects"
        )[0]['c']
        
        linked_projects = self.store.query(
            "SELECT COUNT(*) as c FROM client_projects"
        )[0]['c']
        
        total_clients = self.store.query(
            "SELECT COUNT(*) as c FROM clients"
        )[0]['c']
        
        clients_with_projects = self.store.query(
            "SELECT COUNT(DISTINCT client_id) as c FROM client_projects"
        )[0]['c']
        
        return {
            'total_projects': total_projects,
            'linked_projects': linked_projects,
            'unlinked_projects': total_projects - linked_projects,
            'link_rate': round(linked_projects / total_projects * 100, 1) if total_projects > 0 else 0,
            'total_clients': total_clients,
            'clients_with_projects': clients_with_projects
        }


# Test
if __name__ == "__main__":
    linker = ClientLinker()
    
    print("Testing ClientLinker")
    print("-" * 50)
    
    # Get stats before
    stats = linker.get_linking_stats()
    print(f"Before auto-link:")
    print(f"  Linked: {stats['linked_projects']}/{stats['total_projects']} ({stats['link_rate']}%)")
    
    # Run auto-link
    print(f"\nRunning auto-link...")
    results = linker.auto_link_by_name()
    print(f"  Linked: {results['linked']}")
    print(f"  Already linked: {results['already_linked']}")
    print(f"  No match: {results['no_match']}")
    
    # Get stats after
    stats = linker.get_linking_stats()
    print(f"\nAfter auto-link:")
    print(f"  Linked: {stats['linked_projects']}/{stats['total_projects']} ({stats['link_rate']}%)")
