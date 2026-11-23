import pytest

from agent_under_watch import build_system


@pytest.fixture(scope="session", params=["banking", "healthcare"])
def system_factory(request):
    """Returns a function that builds a fresh, small system for one pack (fast for tests)."""
    pack = request.param

    def make():
        return build_system(pack, normal_per_agent=300, attacks_per_type=5)

    make.pack = pack
    return make
