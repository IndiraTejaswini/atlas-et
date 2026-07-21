"""SSE streaming generator (main._sse_stream) — tested directly against the
async generator rather than through TestClient's HTTP layer. TestClient's
synchronous stream iteration does not reliably deliver an ASGI disconnect
event when a test stops reading early, which can leave the server-side
generator (and pytest teardown waiting on it) hanging indefinitely. Testing
the generator function in isolation, with a controllable fake request and
zero-length sleep, exercises the exact same logic with a guaranteed bound on
how many iterations run.
"""
import asyncio

from app.main import _sse_stream


class FakeRequest:
    """is_disconnected() returns False for the first `disconnect_after`
    calls, then True — lets a test decide exactly how many loop iterations
    run before the generator must stop."""

    def __init__(self, disconnect_after: int):
        self.calls = 0
        self.disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self.calls += 1
        return self.calls > self.disconnect_after


async def _collect(request, poll_fn, n_expected_checks: int) -> list[str]:
    frames = []
    async for frame in _sse_stream(request, poll_fn, interval_s=0):
        frames.append(frame)
        if len(frames) >= n_expected_checks:
            break  # safety net in case disconnect_after logic doesn't bound it
    return frames


def test_yields_a_data_frame_when_payload_changes():
    req = FakeRequest(disconnect_after=3)
    counter = {"n": 0}

    def poll():
        counter["n"] += 1
        return {"n": counter["n"]}  # changes every call -> always "data:"

    frames = asyncio.run(_collect(req, poll, 5))
    assert len(frames) == 3
    assert all(f.startswith("data: ") for f in frames)
    assert '"n": 1' in frames[0]
    assert '"n": 3' in frames[2]


def test_emits_heartbeat_when_payload_unchanged():
    req = FakeRequest(disconnect_after=3)

    frames = asyncio.run(_collect(req, lambda: {"stable": True}, 5))
    assert len(frames) == 3
    assert frames[0].startswith("data: ")   # first payload is always new
    assert frames[1].startswith(": heartbeat")
    assert frames[2].startswith(": heartbeat")


def test_stops_immediately_when_already_disconnected():
    req = FakeRequest(disconnect_after=0)
    frames = asyncio.run(_collect(req, lambda: {"x": 1}, 5))
    assert frames == []


def test_resumes_data_frames_after_a_change_following_heartbeats():
    req = FakeRequest(disconnect_after=4)
    state = {"phase": 0}

    def poll():
        # same payload for the first 2 calls, then changes
        return {"phase": 0} if state["phase"] < 2 else {"phase": 1}

    def advance_and_poll():
        result = poll()
        state["phase"] += 1
        return result

    frames = asyncio.run(_collect(req, advance_and_poll, 5))
    assert len(frames) == 4
    assert frames[0].startswith("data: ")       # phase 0, first time
    assert frames[1].startswith(": heartbeat")  # phase 0 again, unchanged
    assert frames[2].startswith("data: ")       # phase 1, changed
    assert frames[3].startswith(": heartbeat")  # phase 1 again, unchanged
