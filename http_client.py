"""Official HTTP+JSON transport. Does not start a test or consume a test chance.
Start an official PRACTICE test in its UI, then supply its logged-in robot ID.
"""
import json
import time
import uuid
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.request import build_opener, ProxyHandler, Request
from urllib.error import URLError, HTTPError


class OfficialEnv:
    def __init__(self, robot_id, base_url="http://127.0.0.1:2026", log_path="client_log.jsonl"):
        if not robot_id:
            raise ValueError("robot_id must be the currently logged-in team ID")
        self.robot_id = robot_id
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(ProxyHandler({}))
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        self.deadline = None
        self.last_virtual_time_s = 0.

    def _call(self, action, **fields):
        body = dict(arena_id="default",robot_id=self.robot_id,request_id=uuid.uuid4().hex,**fields)
        encoded = json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode("utf-8")
        last_error = None
        for retry in range(4):
            if self.deadline is not None and time.monotonic() >= self.deadline and action != "exit":
                raise TimeoutError("Approaching simulator real-time deadline; stop new actions")
            timeout=12 if self.deadline is None else max(.2,min(12,self.deadline-time.monotonic()+5))
            req = Request(self.base_url+"/"+action,data=encoded,headers={"Content-Type":"application/json"},method="POST")
            t0=time.monotonic()
            try:
                with self.opener.open(req,timeout=timeout) as response:
                    status=response.status
                    result=json.load(response)
            except HTTPError as error:
                # Business or structural errors are not automatically retried.
                raise RuntimeError(f"HTTP {error.code}: {error.read().decode('utf-8',errors='replace')}") from error
            except (URLError,TimeoutError,ConnectionError,OSError,IncompleteRead,RemoteDisconnected,json.JSONDecodeError) as error:
                last_error=error
                if retry < 3:time.sleep(.2*2**retry)
                continue
            with self.log_path.open("a",encoding="utf-8") as stream:
                stream.write(json.dumps(dict(action=action,request=body,response=result,http_status=status,
                                             client_elapsed_s=time.monotonic()-t0),ensure_ascii=False)+"\n")
            if status != 200 or result.get("accepted") is not True:
                raise RuntimeError(f"Simulator rejected /{action}: {result}")
            self.last_virtual_time_s=float(result["virtual_time_s"])
            if action == "enter":
                self.deadline=t0+float(result["remaining_real_duration_s"])-10
            return result
        raise ConnectionError(f"No confirmed response after same-ID retries for /{action}; do not send a replacement action") from last_error

    def enter(self):return self._call("enter")
    def measure(self,x,y,channel):return self._call("measure",position=dict(x=float(x),y=float(y)),channel=int(channel))
    def clear(self,x,y,channel):return self._call("clear",position=dict(x=float(x),y=float(y)),channel=int(channel))
    def exit(self):return self._call("exit")


if __name__ == "__main__":
    import argparse
    from solver import Solver
    p=argparse.ArgumentParser(description="Connect to an already-started official simulator session")
    p.add_argument("--robot-id",required=True)
    p.add_argument("--mode",type=int,choices=[3,4],required=True)
    p.add_argument("--url",default="http://127.0.0.1:2026")
    p.add_argument("--log",default="client_log.jsonl")
    a=p.parse_args()
    env=OfficialEnv(a.robot_id,a.url,a.log)
    print(json.dumps(Solver(env,mode=a.mode).run(),ensure_ascii=False,default=str))
