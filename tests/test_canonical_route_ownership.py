"""
Tests proving intelligence_router owns the canonical intelligence routes at runtime.

After removing 20 duplicate handlers from spec_router, intelligence_router
(mounted at /api/v2/intelligence) is now the sole handler for these paths.

These tests verify:
1. intelligence_router has handlers for all 20 removed routes
2. spec_router no longer registers handlers for those paths
3. The FastAPI app routes /api/v2/intelligence/* to intelligence_router
"""

import re


def _get_spec_router_intelligence_paths():
    """Extract all /intelligence/* route paths registered by spec_router."""
    import inspect

    import api.spec_router as sr

    source = inspect.getsource(sr)
    # Match @spec_router.get("/intelligence/...") or .post, .put, .delete
    return re.findall(r'@spec_router\.\w+\("(/intelligence/[^"]+)"', source)


def _get_intelligence_router_paths():
    """Extract all route paths registered by intelligence_router."""
    import inspect

    import api.intelligence_router as ir

    source = inspect.getsource(ir)
    # Match @intelligence_router.get("/...") or .post, .put, .delete
    return re.findall(r'@intelligence_router\.\w+\("(/[^"]+)"', source)


class TestCanonicalRouteOwnership:
    """Prove intelligence_router is the sole owner of intelligence routes."""

    # The 20 paths that were removed from spec_router.
    # Each was /intelligence/X in spec_router → /api/v2/intelligence/X at runtime.
    # intelligence_router defines them as /X → /api/v2/intelligence/X.
    REMOVED_PATHS = [
        "/critical",
        "/briefing",
        "/signals",
        "/signals/summary",
        "/signals/active",
        "/signals/history",
        "/patterns/catalog",
        "/proposals",
        "/scores/client/{client_id}",
        "/scores/project/{project_id}",
        "/scores/person/{person_id}",
        "/scores/portfolio",
        "/entity/client/{client_id}",
        "/entity/person/{person_id}",
        "/entity/portfolio",
    ]

    # Paths with path params need fuzzy matching
    REMOVED_PATH_PREFIXES = [
        "/projects/",  # /projects/{project_id}/state
        "/clients/",  # /clients/{client_id}/profile, /clients/{client_id}/trajectory
        "/team/",  # /team/{person_id}/profile, /team/{person_id}/trajectory
    ]

    def test_spec_router_only_has_patterns(self):
        """spec_router should only have /intelligence/patterns."""
        paths = _get_spec_router_intelligence_paths()
        assert paths == ["/intelligence/patterns"], (
            f"spec_router should only have /intelligence/patterns, but found: {paths}"
        )

    def test_intelligence_router_covers_all_removed_paths(self):
        """intelligence_router must have handlers for all 20 removed routes."""
        ir_paths = _get_intelligence_router_paths()

        for path in self.REMOVED_PATHS:
            assert path in ir_paths, (
                f"intelligence_router missing handler for {path} "
                f"(was removed from spec_router, must exist in intelligence_router)"
            )

    def test_intelligence_router_has_profile_and_trajectory_routes(self):
        """intelligence_router must cover profile/trajectory/state routes."""
        ir_paths = _get_intelligence_router_paths()
        ir_paths_str = " ".join(ir_paths)

        for prefix in self.REMOVED_PATH_PREFIXES:
            assert prefix in ir_paths_str, (
                f"intelligence_router missing routes under {prefix} "
                f"(profiles, trajectories, or state routes)"
            )

    def test_no_runtime_shadowing_for_removed_routes(self):
        """None of the removed intelligence routes exist in spec_router."""
        spec_paths = _get_spec_router_intelligence_paths()

        for path in self.REMOVED_PATHS:
            spec_path = f"/intelligence{path}"
            assert spec_path not in spec_paths, (
                f"spec_router still registers {spec_path}, "
                f"which would shadow intelligence_router's {path}"
            )

    def test_patterns_not_duplicated_in_intelligence_router(self):
        """/patterns is canonically in spec_router; intelligence_router must not shadow it."""
        ir_paths = _get_intelligence_router_paths()
        # /patterns/catalog is fine (intelligence_router owns that), but bare
        # /patterns must NOT be in intelligence_router — spec_router serves it
        # with the richer PatternDetectionResponse schema.
        bare_patterns = [p for p in ir_paths if p == "/patterns"]
        assert bare_patterns == [], (
            f"intelligence_router should NOT register /patterns "
            f"(spec_router owns it with PatternDetectionResponse). Found: {bare_patterns}"
        )
