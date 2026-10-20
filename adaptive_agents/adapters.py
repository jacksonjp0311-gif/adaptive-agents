"""Reference host bridge. Never executes tools or sends external messages itself."""
from typing import Protocol

class PegasusHost(Protocol):
    def discover_tools(self, project_id: str) -> list[dict]: ...
    def request_tool(self, instance_id: str, tool_id: str, arguments: dict) -> dict: ...
    def start(self, spec: dict) -> None: ...
    def cancel(self, instance_id: str) -> None: ...
    def dispose_context(self, instance_id: str) -> None: ...

class ScopedMessages:
    def __init__(self, lifecycle, max_messages=32):
        if type(max_messages) is not int or not 1 <= max_messages <= 256: raise ValueError("invalid message budget")
        self.life, self.maximum = lifecycle, max_messages

    def send(self, source, target, text, *, message_id):
        from .core import ident
        ident(message_id)
        a, state_a, events = self.life._load(source)
        b, state_b, _ = self.life._load(target)
        if (a["project_id"],a["assignment_id"]) != (b["project_id"],b["assignment_id"]):
            raise ValueError("cross-assignment communication rejected")
        payload={"message_id":message_id,"target_instance_id":target,"text":text}
        old=[e for e in events if e["type"]=="message"]
        duplicate=next((e for e in old if e["payload"]["message_id"]==message_id),None)
        if duplicate:
            if duplicate["payload"]!=payload: raise ValueError("message identity conflict")
            return duplicate["event_id"]
        # A recipient's legacy ACK key must identify only one sender's message.
        inbound_events=[e for e in self.life.store.events() if e["type"]=="message" and e["payload"]["target_instance_id"]==target]
        if any(e["payload"]["message_id"]==message_id for e in inbound_events):
            raise ValueError("recipient message identity conflict")
        if state_a!="running" or state_b!="running": raise ValueError("participants must be running")
        if not isinstance(text,str) or not text.strip() or len(text)>2000 or len(old)>=self.maximum:
            raise ValueError("message size or budget exceeded")
        inbound=len(inbound_events)
        if inbound>=self.maximum: raise ValueError("recipient queue budget exhausted")
        if not self.life.step(source): raise ValueError("execution budget exhausted")
        return self.life.store.append(a,"message",payload,self.life.clock())

    def inbox(self, target):
        spec, _, _ = self.life._load(target)
        return [e for e in self.life.store.events() if e["type"]=="message" and e["project_id"]==spec["project_id"] and e["assignment_id"]==spec["assignment_id"] and e["payload"]["target_instance_id"]==target][:self.maximum]

    def acknowledge(self, target, message_id, *, source_instance_id=None):
        spec, _, events = self.life._load(target)
        # Search durable records, not the bounded presentation slice of inbox().
        matches=[e for e in self.life.store.events() if e["type"]=="message"
                 and e["project_id"]==spec["project_id"] and e["assignment_id"]==spec["assignment_id"]
                 and e["payload"]["target_instance_id"]==target and e["payload"]["message_id"]==message_id
                 and (source_instance_id is None or e["instance_id"]==source_instance_id)]
        if not matches: raise ValueError("message not owned by recipient")
        if len(matches)!=1: raise ValueError("ambiguous message identity; specify source_instance_id")
        message=matches[0]
        prior=next((e for e in events if e["type"]=="message_ack" and e["payload"]["message_event_id"]==message["event_id"]),None)
        if prior: return prior["event_id"]
        return self.life.store.append(spec,"message_ack",{"message_event_id":message["event_id"]},self.life.clock())
