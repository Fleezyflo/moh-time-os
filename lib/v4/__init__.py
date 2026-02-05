"""
Time OS V4 - Executive Operating System

Complete service architecture:

Milestone 1 - Truth & Proof Backbone:
- ArtifactService: Normalized evidence stream
- IdentityService: Identity resolution
- EntityLinkService: Graph linking + Fix Data queue

Milestone 2 - Signals & Proposals:
- SignalService: Signal management and detector runs
- ProposalService: Proposal bundling and surfacing

Milestone 3 - Issues (Monitored Loops):
- IssueService: Issue tracking, watchers, handoffs, decisions

Milestone 4 - Intersections, Reports & Policy:
- CouplingService: Entity intersection analysis
- ReportService: Template-based report generation
- PolicyService: ACL, retention, redaction
"""

from .artifact_service import ArtifactService, get_artifact_service
from .identity_service import IdentityService, get_identity_service
from .entity_link_service import EntityLinkService, get_entity_link_service
from .signal_service import SignalService, get_signal_service
from .proposal_service import ProposalService, get_proposal_service
from .issue_service import IssueService, get_issue_service
from .coupling_service import CouplingService, get_coupling_service
from .report_service import ReportService, get_report_service
from .policy_service import PolicyService, get_policy_service

__all__ = [
    # M1: Truth & Proof
    'ArtifactService', 'get_artifact_service',
    'IdentityService', 'get_identity_service',
    'EntityLinkService', 'get_entity_link_service',
    # M2: Signals & Proposals
    'SignalService', 'get_signal_service',
    'ProposalService', 'get_proposal_service',
    # M3: Issues
    'IssueService', 'get_issue_service',
    # M4: Intersections, Reports, Policy
    'CouplingService', 'get_coupling_service',
    'ReportService', 'get_report_service',
    'PolicyService', 'get_policy_service',
]
