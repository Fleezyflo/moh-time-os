"""
Extractors — Per-domain raw data extraction.

Each extractor is responsible for:
1. Querying raw data from source (DB, API, etc.)
2. Converting to domain model instances
3. NOT resolving references (that's in resolvers.py)

Extractors will be implemented as needed per domain:
- projects.py: Asana projects extraction
- clients.py: Xero contacts extraction
- invoices.py: Xero invoices extraction
- commitments.py: NLP-extracted commitments
- communications.py: Email/chat thread extraction
- people.py: Team member extraction
"""

# Extractors will be added here as implemented
__all__ = []
