"""Pinned guard with explicit request-settlement bookkeeping for resume."""
from __future__ import annotations
from .vendor import interface as old, InterfaceFailure


class PublicLedger(old.MeteredInterface):
    def __init__(self, backend, guard=None, clock=None):
        kwargs = dict(guard=guard)
        if clock is not None:
            kwargs['clock'] = clock
        super().__init__(backend, **kwargs)
        self.timing_settled_through_event_count = 0
        self.inflight_request = None
        self.unknown_backend_failure = None

    def _invoke(self, function, *args):
        if self.unknown_backend_failure is not None:
            raise InterfaceFailure('Interface disabled after unresolved backend failure')
        if self.inflight_request is not None:
            raise InterfaceFailure('Overlapping business requests are forbidden')
        self.inflight_request = tuple(args)
        try:
            return super()._invoke(function, *args)
        except BaseException as exc:
            # A timeout is not proof that the physical action was rejected.
            # Do not allow Engine's controller-recovery handler to retry/fallback.
            self.unknown_backend_failure = type(exc).__name__ + ': ' + str(exc)
            raise InterfaceFailure('Backend call failed; acceptance unresolved: ' + self.unknown_backend_failure) from exc
        finally:
            self.inflight_request = None

    def _response(self, action, request, raw, previous, expected):
        count = len(self.events)
        try:
            return super()._response(action, request, raw, previous, expected)
        finally:
            if len(self.events) == count + 1:
                event = self.events[-1]
                if all(event.get(k) == v for k, v in self._pending_timing.items()):
                    self.timing_settled_through_event_count = len(self.events)
