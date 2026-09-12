"""Independent, rule-based LOCAL simulator. This is not the official simulator.

Seeds define an assumed experimental distribution, not official hidden cases.
The solver receives only enter/measure/clear/exit responses.
"""
from dataclasses import dataclass
import math
import random
import time
import hashlib


@dataclass
class Source:
    channel: int
    x: float
    y: float
    radius: float
    direction: float | None = None
    cleared: bool = False


def make_case(seed, mode=3, scenario="random"):
    r = random.Random(seed)
    n = r.randint(10, 16)
    channels = r.sample(range(1, 21), n)
    nd = 0 if mode == 3 else r.randint(1, n-1)
    out = []
    for i, ch in enumerate(channels):
        a = r.uniform(-math.pi, math.pi)
        rad = 1800*math.sqrt(r.random())
        rx = r.uniform(1000, 1500)
        direction = r.uniform(-math.pi, math.pi) if i < nd else None
        if scenario == "boundary":
            rad = 1799.999 if i % 2 else 1800
            rx = 1000
            direction = a if mode == 4 else None
        elif scenario == "cluster":
            rad = r.uniform(0, 60)
            rx = 1000
            direction = a+math.pi/2 if mode == 4 else None
        elif scenario == "min_radius":
            rx = 1000
            direction = r.uniform(-math.pi, math.pi) if mode == 4 else None
        out.append(Source(ch, rad*math.cos(a), rad*math.sin(a), rx, direction))
    return out


class LocalEnv:
    def __init__(self, sources, seed=0, noise="uniform", keep_log=True,
                 clock=time.monotonic, window_elapsed_s=0):
        self._clock = clock
        self._ready_at = clock() - window_elapsed_s
        self.exit_reason = None
        self._virtual_us = 0
        self._sources = {s.channel: Source(**vars(s)) for s in sources}
        self.seed, self.noise = seed, noise
        self.position = (0., 0.)
        self.channel = 1
        self.virtual_time_s = 0.
        self.distance = 0.
        self.switches = self.measures = self.clear_attempts = self.successes = 0
        self.log = []
        self.keep_log = keep_log
        self.started = self.finished = False
        self.runtime_s = 0.

    def _response(self, action, request, duration=0., **fields):
        # Frozen local convention: round each action to nearest microsecond.
        # The official documentation specifies microseconds, not its tie rule.
        self._virtual_us += int(math.floor(duration * 1_000_000 + 0.5))
        self.virtual_time_s = self._virtual_us / 1_000_000
        result = dict(accepted=True, real_timestamp_ms=round(time.time()*1000),
                      virtual_time_s=self.virtual_time_s, **fields)
        if self.keep_log:
            self.log.append(dict(action=action, request=request, response=result.copy()))
        if self.virtual_time_s >= 360000:
            self._finish("virtual_timeout")
        elif self.started and self._clock() >= self._deadline:
            self._finish("real_timeout")
        return result

    def _move(self, x, y):
        # Parameters and state were checked atomically before movement.
        d = math.hypot(x-self.position[0], y-self.position[1])
        self.distance += d
        self.position = (float(x), float(y))
        return d/5

    def _finish(self, reason):
        self.finished = True
        self.exit_reason = reason
        self.runtime_s = max(0., self._clock()-self._t0) if self.started else 0.

    def _guard(self):
        if self.finished:
            raise ConnectionError("local interface closed: " + str(self.exit_reason))
        if self._clock() >= self._ready_at + 1500:
            self._finish("window_timeout")
            raise ConnectionError("local test window closed")
        if self.started and (self._clock() >= self._deadline or self.virtual_time_s >= 360000):
            self._finish("real_timeout" if self._clock() >= self._deadline else "virtual_timeout")
            raise ConnectionError("local time limit closed the interface")

    def _reject(self):
        return dict(accepted=False, real_timestamp_ms=round(time.time()*1000), virtual_time_s=0)

    @staticmethod
    def _parameters(x,y,channel):
        def number(v):
            return type(v) in (int,float) and math.isfinite(v)
        if not all(number(v) and abs(v) <= 2e6 for v in (x,y)):
            raise ValueError("HTTP 400 equivalent: invalid position")
        if not number(channel) or int(channel) != channel or not 1 <= channel <= 20:
            raise ValueError("HTTP 400 equivalent: invalid channel")
        return int(channel)

    def enter(self):
        self._guard()
        if self.started:
            return self._reject()
        self.started = True
        self._t0 = self._clock()
        self._deadline = min(self._t0+1200, self._ready_at+1500)
        remaining = max(0,math.floor(self._deadline-self._t0))
        return self._response("enter", {}, max_virtual_duration_s=360000,
                              max_real_duration_s=1200, remaining_real_duration_s=remaining)

    def error(self, x, y, channel):
        # Same coordinate, same channel => identical local error, including revisits.
        x,y = (0.0 if x == 0 else float(x)), (0.0 if y == 0 else float(y))
        if self.noise.startswith("cell_"):
            size = int(self.noise.split("_")[1])
            key = f"{self.seed}|{math.floor(x/size)}|{math.floor(y/size)}".encode()
            z = int.from_bytes(hashlib.sha256(key).digest()[:8],"big")/(2**64-1)
            return 2*z-1
        if self.noise == "smooth_shared":
            return math.sin(x/400+y/350+self.seed*.017)
        if self.noise == "positive":
            return 1.
        if self.noise == "negative":
            return -1.
        if self.noise == "smooth":
            return math.sin(x/173+y/211+self.seed*.007+channel)
        b = f"{self.seed}|{channel}|{float(x).hex()}|{float(y).hex()}".encode()
        z = int.from_bytes(hashlib.blake2b(b,digest_size=8).digest(),"big")/(2**64-1)
        return 2*z-1

    def measure(self, x, y, channel):
        channel = self._parameters(x,y,channel)
        self._guard()
        if not self.started:
            return self._reject()
        duration = self._move(x,y)+5+(channel != self.channel)
        self.switches += channel != self.channel
        self.channel = channel
        self.measures += 1
        s = self._sources.get(channel)
        fields = {"measure_result":"no_signal"}
        if s and not s.cleared:
            dx,dy = x-s.x,y-s.y
            d = math.hypot(dx,dy)
            visible = (s.direction is None or
                       dx*math.cos(s.direction)+dy*math.sin(s.direction) >= -1e-10)
            if d <= s.radius+1e-10 and visible:
                if d <= 5:
                    fields = {"measure_result":"near"}
                else:
                    theta = math.degrees(math.atan2(-dy,-dx))+self.error(x,y,channel)
                    fields = {"measure_result":"direction", "svd_deg":round(theta%360,2)%360}
        return self._response("measure",dict(position={"x":x,"y":y},channel=channel),
                              duration,**fields)

    def clear(self, x, y, channel):
        channel = self._parameters(x,y,channel)
        self._guard()
        if not self.started:
            return self._reject()
        duration = self._move(x,y)+3
        self.clear_attempts += 1
        s = self._sources.get(channel)
        ok = bool(s and not s.cleared and math.hypot(x-s.x,y-s.y) <= 20+1e-10)
        if ok:
            s.cleared = True
            self.successes += 1
            duration += 2
        return self._response("clear",dict(position={"x":x,"y":y},channel=channel),
                              duration,clear_result="success" if ok else "no_target_in_range")

    def exit(self):
        self._guard()
        if not self.started:
            return self._reject()
        self._finish("user_exit")
        return self._response("exit",{},exit_reason="user_exit")

    def stats(self):
        n = len(self._sources)
        independent_time = self.distance/5 + self.switches + self.measures*5 + self.clear_attempts*3+self.successes*2
        return dict(n=n, cleared=self.successes, fraction=self.successes/n if n else None,
                    time_s=self.virtual_time_s, average_s=self.virtual_time_s/self.successes if self.successes else None,
                    distance_m=self.distance, measures=self.measures, switches=self.switches,
                    clear_attempts=self.clear_attempts, clear_failures=self.clear_attempts-self.successes,
                    runtime_s=self.runtime_s, accounting_error_s=abs(independent_time-self.virtual_time_s))


class InterfaceOnly:
    """Only these four bound callables are visible to normal strategy code."""
    def __init__(self, env):
        self.enter, self.measure, self.clear, self.exit = env.enter, env.measure, env.clear, env.exit
