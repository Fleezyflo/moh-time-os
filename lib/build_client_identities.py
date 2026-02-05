"""
Build Client Identities Registry

Populates client_identities table with email domains mapped to clients.
This enables the normalizer to link communications to clients.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import uuid

DB_PATH = Path(__file__).parent.parent / "data" / "state.db"

# Known domain → client mappings
KNOWN_DOMAINS = {
    # GMG brands
    'gmg.ae': 'GMG Consumer LLC',
    'gmgretail.com': 'GMG Consumer LLC',
    
    # Gargash
    'gargash.com': 'Gargash Enterprises L.L.C',
    'gargashinsurance.com': 'Gargash Enterprises L.L.C',
    
    # Pharmacies
    'supercarepharmacy.com': 'Super Care Pharmacy L.L.C',
    'supercare.ae': 'Super Care Pharmacy L.L.C',
    'binsina.com': 'BinSina Pharmacy L.L.C',
    'binsinapharma.com': 'BinSina Pharmacy L.L.C',
    
    # Retail/Services
    'sixt.ae': 'SIXT Rent a Car LLC',
    'sixt.com': 'SIXT Rent a Car LLC',
    'fiveguys.ae': 'Five Guys',
    'fiveguys.com': 'Five Guys',
    'asics.com': 'ASICS ARABIA FZE',
    'chalhoub.com': 'Chalhoub Inc. FZE',
    'deliveroo.ae': 'Deliveroo',
    'deliveroo.com': 'Deliveroo',
    'redbull.com': 'Red Bull',
    
    # Sun & Sand Sports
    'sssports.com': 'Sun & Sand Sports',
    'sunandsandsports.com': 'Sun & Sand Sports',
}

# Known email → client mappings (specific contacts)
KNOWN_EMAILS = {
    # Add specific email addresses if known
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_client_id_by_name(conn, name: str) -> str:
    """Find client ID by name (fuzzy match)."""
    cursor = conn.cursor()
    
    # Try exact match first
    cursor.execute("SELECT id FROM clients WHERE LOWER(name) = LOWER(?)", (name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    
    # Try contains match
    cursor.execute("SELECT id FROM clients WHERE LOWER(name) LIKE LOWER(?)", (f'%{name}%',))
    row = cursor.fetchone()
    if row:
        return row['id']
    
    return None


def build_from_known_mappings(conn) -> int:
    """Build identities from known domain mappings."""
    cursor = conn.cursor()
    inserted = 0
    now = datetime.now().isoformat()
    
    for domain, client_name in KNOWN_DOMAINS.items():
        client_id = get_client_id_by_name(conn, client_name)
        if not client_id:
            print(f"  Warning: Client not found for domain {domain}: {client_name}")
            continue
        
        # Check if already exists
        cursor.execute("""
            SELECT id FROM client_identities 
            WHERE client_id = ? AND identity_type = 'domain' AND LOWER(identity_value) = LOWER(?)
        """, (client_id, domain))
        
        if cursor.fetchone():
            continue
        
        # Insert
        cursor.execute("""
            INSERT INTO client_identities (id, client_id, identity_type, identity_value, created_at)
            VALUES (?, ?, 'domain', ?, ?)
        """, (str(uuid.uuid4()), client_id, domain.lower(), now))
        inserted += 1
    
    conn.commit()
    return inserted


def build_from_invoice_contacts(conn) -> int:
    """Build identities by matching invoice contacts to communication domains."""
    cursor = conn.cursor()
    inserted = 0
    now = datetime.now().isoformat()
    
    # Get clients with invoices
    cursor.execute("""
        SELECT DISTINCT i.client_id, i.client_name, c.name as db_client_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.client_id IS NOT NULL
    """)
    invoice_clients = cursor.fetchall()
    
    for ic in invoice_clients:
        client_id = ic['client_id']
        client_name = ic['client_name'] or ic['db_client_name']
        
        if not client_name:
            continue
        
        # Find communications that might be from this client
        # Look for subject lines mentioning client name
        name_parts = client_name.lower().split()
        for part in name_parts:
            if len(part) < 4:  # Skip short words
                continue
            
            cursor.execute("""
                SELECT DISTINCT 
                    LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) as domain
                FROM communications
                WHERE from_email LIKE '%@%'
                AND (
                    LOWER(subject) LIKE ? 
                    OR LOWER(from_email) LIKE ?
                )
                AND LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) NOT LIKE '%hrmny%'
                AND LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) NOT LIKE '%google%'
                AND LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) NOT LIKE '%gmail%'
            """, (f'%{part}%', f'%{part}%'))
            
            domains = cursor.fetchall()
            for d in domains:
                domain = d['domain']
                if not domain or len(domain) < 4:
                    continue
                
                # Check if already exists
                cursor.execute("""
                    SELECT id FROM client_identities 
                    WHERE client_id = ? AND identity_type = 'domain' AND LOWER(identity_value) = LOWER(?)
                """, (client_id, domain))
                
                if cursor.fetchone():
                    continue
                
                # Insert with lower confidence (inferred)
                cursor.execute("""
                    INSERT INTO client_identities (id, client_id, identity_type, identity_value, created_at)
                    VALUES (?, ?, 'domain', ?, ?)
                """, (str(uuid.uuid4()), client_id, domain, now))
                inserted += 1
                print(f"  Inferred: {domain} → {client_name}")
    
    conn.commit()
    return inserted


def build_from_project_names(conn) -> int:
    """Build identities by matching project names to communication domains."""
    cursor = conn.cursor()
    inserted = 0
    now = datetime.now().isoformat()
    
    # Get projects with client_id
    cursor.execute("""
        SELECT p.id, p.name, p.client_id, c.name as client_name
        FROM projects p
        JOIN clients c ON p.client_id = c.id
        WHERE p.client_id IS NOT NULL
        AND p.is_internal = 0
    """)
    projects = cursor.fetchall()
    
    # For each project, look for comms mentioning it
    for proj in projects:
        project_name = proj['name']
        client_id = proj['client_id']
        client_name = proj['client_name']
        
        # Extract key words from project name
        words = [w for w in project_name.lower().split() if len(w) >= 4]
        words = [w for w in words if w not in ('project', 'monthly', 'weekly', 'daily', 'retainer')]
        
        if not words:
            continue
        
        for word in words[:2]:  # Check first 2 meaningful words
            cursor.execute("""
                SELECT DISTINCT 
                    LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) as domain
                FROM communications
                WHERE from_email LIKE '%@%'
                AND LOWER(subject) LIKE ?
                AND LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) NOT LIKE '%hrmny%'
                AND LOWER(SUBSTR(from_email, INSTR(from_email, '@') + 1)) NOT LIKE '%google%'
            """, (f'%{word}%',))
            
            domains = cursor.fetchall()
            for d in domains:
                domain = d['domain']
                if not domain or len(domain) < 4:
                    continue
                
                # Check if already exists
                cursor.execute("""
                    SELECT id FROM client_identities 
                    WHERE identity_type = 'domain' AND LOWER(identity_value) = LOWER(?)
                """, (domain,))
                
                if cursor.fetchone():
                    continue
                
                # Insert with lower confidence
                cursor.execute("""
                    INSERT INTO client_identities (id, client_id, identity_type, identity_value, created_at)
                    VALUES (?, ?, 'domain', ?, ?)
                """, (str(uuid.uuid4()), client_id, domain, now))
                inserted += 1
    
    conn.commit()
    return inserted


def run():
    """Run full identity building process."""
    conn = get_conn()
    
    print("Building client identities...")
    
    # Count before
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM client_identities")
    before = cursor.fetchone()['cnt']
    
    # Build from known mappings
    print("\n1. Known domain mappings...")
    known = build_from_known_mappings(conn)
    print(f"   Inserted: {known}")
    
    # Build from invoice contacts
    print("\n2. Invoice contact inference...")
    invoice = build_from_invoice_contacts(conn)
    print(f"   Inserted: {invoice}")
    
    # Build from project names
    print("\n3. Project name inference...")
    project = build_from_project_names(conn)
    print(f"   Inserted: {project}")
    
    # Count after
    cursor.execute("SELECT COUNT(*) as cnt FROM client_identities")
    after = cursor.fetchone()['cnt']
    
    print(f"\nTotal identities: {before} → {after} (+{after - before})")
    
    # Show what we have
    cursor.execute("""
        SELECT ci.identity_value as domain, c.name as client
        FROM client_identities ci
        JOIN clients c ON ci.client_id = c.id
        WHERE ci.identity_type = 'domain'
        ORDER BY c.name
    """)
    rows = cursor.fetchall()
    print(f"\nDomain → Client mappings ({len(rows)}):")
    for r in rows:
        print(f"  {r['domain']:30} → {r['client'][:40]}")
    
    conn.close()
    return after - before


if __name__ == '__main__':
    run()
