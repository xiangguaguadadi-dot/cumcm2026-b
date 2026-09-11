"""Four-call interface ledger and irreversible primitive guard.

The underlying adapter remains responsible for its own idempotent transport
retries. A returned business response is accounted exactly once by this layer.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import time

class FallbackRequired(Exception):
    pass

class InterfaceFailure(RuntimeError):
    pass

@dataclass(frozen=True)
class GuardConfig:
    box_m: float = 4000.
    learning_time_limit_s: float = 300000.
    learning_request_cap: int = 10000
    no_progress_limit: int = 32
    fallback_reserve_s: float = 53000.
    primitive_max_s: float = 2300.
    real_reserve_s: float = 30.  # empirical engineering reserve, not a theorem
    deterministic_request_bound_s: float | None = None
    deterministic_fallback_compute_s: float = 0.
    accounting_tolerance_s: float = 0.00002

    def __post_init__(self):
        for name in ('box_m','learning_time_limit_s','fallback_reserve_s','primitive_max_s',
                     'real_reserve_s','deterministic_fallback_compute_s','accounting_tolerance_s'):
            value=getattr(self,name)
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError('Invalid finite nonnegative guard field: '+name)
        for name in ('learning_request_cap','no_progress_limit'):
            if type(getattr(self,name)) is not int:raise ValueError('Guard count must be an integer: '+name)
        if (self.deterministic_request_bound_s is not None and
            (type(self.deterministic_request_bound_s) not in (int,float) or
             not math.isfinite(self.deterministic_request_bound_s) or self.deterministic_request_bound_s<0)):
            raise ValueError('Invalid deterministic request bound')
        if not 0 < self.box_m <= 4000:raise ValueError('box exceeds proved contract')
        if not 0 <= self.learning_time_limit_s <= 300000:raise ValueError('time cap exceeds contract')
        if not 0 <= self.learning_request_cap <= 10000:raise ValueError('request cap exceeds contract')
        if not 1 <= self.no_progress_limit <= 32:raise ValueError('progress cap exceeds contract')
        if self.fallback_reserve_s < 53000:raise ValueError('fallback reserve too small')
        if self.primitive_max_s < 2300:raise ValueError('primitive bound too small')
        if self.real_reserve_s < 0:raise ValueError('negative real reserve')

class MeteredInterface:
    RESPONSE_KEYS=frozenset(('accepted','real_timestamp_ms','virtual_time_s',
        'max_virtual_duration_s','max_real_duration_s','remaining_real_duration_s',
        'measure_result','svd_deg','clear_result','exit_reason'))

    def __init__(self, backend, guard=None, clock=time.monotonic):
        # Deliberately retain callables only; do not inspect the backing env.
        self._enter=backend.enter;self._measure=backend.measure
        self._clear=backend.clear;self._exit=backend.exit
        self.guard=guard or GuardConfig();self.clock=clock
        self.position=(0.,0.);self.channel=1;self.virtual_time=0.
        self.events=[];self.cleared=set();self.positive_observations=set()
        self.started=False;self.exited=False;self.started_at=None;self.deadline=None
        self.phase='learning';self.takeover_reason=None;self.learning_requests=0
        self.exit_certificate=None;self.accounting_max_error_s=0.
        self._last_response_at=None;self._pending_timing={}

    @property
    def elapsed_real_s(self):
        return 0. if self.started_at is None else max(0.,self.clock()-self.started_at)

    @property
    def remaining_real_s(self):
        return 1200. if self.deadline is None else max(0.,self.deadline-self.clock())

    def request_takeover(self, reason):
        if self.takeover_reason is None:self.takeover_reason=str(reason)
        raise FallbackRequired(self.takeover_reason)

    def check_learning(self, target=None):
        if self.phase!='learning':return
        if self.takeover_reason:self.request_takeover(self.takeover_reason)
        g=self.guard
        if target is not None:
            if (not all(math.isfinite(v) for v in target)
                    or any(abs(v)>g.box_m for v in target)):
                self.request_takeover('learning_endpoint_outside_box')
        if self.virtual_time>=g.learning_time_limit_s:
            self.request_takeover('learning_virtual_time_cap')
        if self.learning_requests>=g.learning_request_cap:
            self.request_takeover('learning_primitive_cap')
        if self.virtual_time+g.primitive_max_s+g.fallback_reserve_s>=360000:
            self.request_takeover('fallback_virtual_reserve')
        real_reserve=g.real_reserve_s
        if g.deterministic_request_bound_s is not None:
            real_reserve=max(real_reserve,5846*g.deterministic_request_bound_s+
                             g.deterministic_fallback_compute_s)
        if self.started and self.remaining_real_s<=real_reserve:
            self.request_takeover('fallback_real_reserve')

    def _invoke(self, function, *args):
        t0=self.clock()
        compute=0. if self._last_response_at is None else max(0.,t0-self._last_response_at)
        try:return function(*args)
        finally:
            t1=self.clock();self._last_response_at=t1
            self._pending_timing={'compute_since_previous_response_s':compute,
                                  'backend_call_s':max(0.,t1-t0)}

    def _response(self, action, request, raw, previous, expected):
        response={k:v for k,v in raw.items() if k in self.RESPONSE_KEYS}
        if response.get('accepted') is not True:
            raise InterfaceFailure('Business request rejected: '+action)
        now=float(response.get('virtual_time_s',previous))
        if not math.isfinite(now) or now<previous-1e-8:
            raise InterfaceFailure('Invalid or decreasing virtual time')
        delta=now-previous
        error=abs(delta-expected)
        self.accounting_max_error_s=max(self.accounting_max_error_s,error)
        self.virtual_time=now
        self.events.append({'index':len(self.events),'phase':self.phase,
            'action':action,'request':request,'response':response.copy(),
            'delta_time_s':delta,'expected_time_s':expected,'accounting_error_s':error,
            **self._pending_timing})
        # Accepted effects are retained even if later validation fails.
        if error>self.guard.accounting_tolerance_s:
            raise InterfaceFailure('Primitive cost mismatch: '+action)
        return response

    def enter(self):
        if self.started:raise InterfaceFailure('Wrapper must not enter twice')
        t=self.clock();r=self._response('enter',{},self._invoke(self._enter),self.virtual_time,0.)
        self.started=True;self.started_at=t
        remaining=float(r.get('remaining_real_duration_s',1200.))
        self.deadline=t+max(0.,min(1200.,remaining))
        return r

    def _validate_request(self,x,y,ch):
        if type(ch) not in (int,float) or isinstance(ch,bool) or int(ch)!=ch or not 1<=ch<=20:
            raise InterfaceFailure('Invalid channel')
        if type(x) not in (int,float) or type(y) not in (int,float):
            raise InterfaceFailure('Invalid coordinate type')
        p=(float(x),float(y))
        if not all(math.isfinite(v) and abs(v)<=2e6 for v in p):
            raise InterfaceFailure('Invalid coordinate')
        return p,int(ch)

    def _post_guard(self):
        # Check immediately after each accepted primitive. If it trips before
        # C7 consumes the reply, the ledger still has authoritative effects.
        if self.phase=='learning':self.check_learning()

    def measure(self,x,y,ch):
        p,ch=self._validate_request(x,y,ch);self.check_learning(p)
        before=self.virtual_time
        expected=math.dist(self.position,p)/5+5+int(ch!=self.channel)
        raw=self._invoke(self._measure,p[0],p[1],ch)
        if raw.get('accepted') is True:
            self.position=p;self.channel=ch
            if self.phase=='learning':self.learning_requests+=1
        r=self._response('measure',{'position':{'x':p[0],'y':p[1]},'channel':ch},raw,before,expected)
        kind=r.get('measure_result')
        if kind not in ('direction','near','no_signal'):raise InterfaceFailure('Unknown measurement result')
        if kind=='direction' and not math.isfinite(float(r.get('svd_deg',float('nan')))):
            raise InterfaceFailure('Invalid bearing')
        if kind in ('direction','near'):
            self.positive_observations.add((ch,p[0],p[1],kind))
        self._post_guard();return r

    def clear(self,x,y,ch):
        p,ch=self._validate_request(x,y,ch);self.check_learning(p)
        before=self.virtual_time
        base=math.dist(self.position,p)/5+3
        raw=self._invoke(self._clear,p[0],p[1],ch)
        success=raw.get('clear_result')=='success'
        if raw.get('accepted') is True:
            self.position=p
            if success:self.cleared.add(ch)
            if self.phase=='learning':self.learning_requests+=1
        r=self._response('clear',{'position':{'x':p[0],'y':p[1]},'channel':ch},raw,before,base+2*success)
        if r.get('clear_result') not in ('success','no_target_in_range'):
            raise InterfaceFailure('Unknown clear result')
        if len(self.cleared)>16:raise InterfaceFailure('Public source-count upper bound contradicted')
        self._post_guard();return r

    def exit(self):
        if self.exit_certificate is None:raise InterfaceFailure('No completion certificate for EXIT')
        r=self._response('exit',{},self._invoke(self._exit),self.virtual_time,0.)
        self.exited=True;return r

    def start_fallback(self, reason):
        self.phase='fallback'
        if self.takeover_reason is None:self.takeover_reason=str(reason)
