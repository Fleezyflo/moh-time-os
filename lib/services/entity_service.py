"""
Entity Service Facade

Provides unified lazy-singleton access to V4 services:
- IssueService
- SignalService
- ProposalService
- CouplingService

Prevents direct imports of V4 services in API handlers.
"""

from lib.v4.coupling_service import CouplingService
from lib.v4.issue_service import IssueService
from lib.v4.proposal_service import ProposalService
from lib.v4.signal_service import SignalService

_instance: "EntityServiceFacade | None" = None


class EntityServiceFacade:
    """Unified facade for V4 services."""

    def __init__(self):
        self._issue_service: IssueService | None = None
        self._signal_service: SignalService | None = None
        self._proposal_service: ProposalService | None = None
        self._coupling_service: CouplingService | None = None

    @property
    def issues(self) -> IssueService:
        """Get or create IssueService singleton."""
        if self._issue_service is None:
            self._issue_service = IssueService()
        return self._issue_service

    @property
    def signals(self) -> SignalService:
        """Get or create SignalService singleton."""
        if self._signal_service is None:
            self._signal_service = SignalService()
        return self._signal_service

    @property
    def proposals(self) -> ProposalService:
        """Get or create ProposalService singleton."""
        if self._proposal_service is None:
            self._proposal_service = ProposalService()
        return self._proposal_service

    @property
    def coupling(self) -> CouplingService:
        """Get or create CouplingService singleton."""
        if self._coupling_service is None:
            self._coupling_service = CouplingService()
        return self._coupling_service


def get_entity_service() -> EntityServiceFacade:
    """Get global EntityServiceFacade singleton."""
    global _instance
    if _instance is None:
        _instance = EntityServiceFacade()
    return _instance
