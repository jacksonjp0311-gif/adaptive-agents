from __future__ import annotations
import hashlib
import json
import math
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Protocol

TERMINAL = {"completed", "failed", "cancelled", "timed_out"}

def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r"[\w.:-]{1,160}", value):
        raise ValueError("invalid identifier")
    return value

@dataclass(frozen=True)
class Assignment:
    assignment_id: str
    project_id: str
    job_name: str
    objective: str
    role: str
    context: str = ""
    chat_id: str = ""
    task_id: str = ""
    template_id: str = ""
    configuration_hash: str = ""
    requested_tools: tuple = ()
    max_steps: int = 20
    timeout_seconds: float = 300
    lesson_keys: tuple = ()
    copy_run: dict = field(default_factory=dict)

    def __post_init__(self):
        ident(self.assignment_id); ident(self.project_id)
        for value in (self.chat_id, self.task_id, self.template_id):
            if value: ident(value)
        if self.configuration_hash and not re.fullmatch(r"[a-f0-9]{64}", self.configuration_hash): raise ValueError("invalid configuration_hash")
        for name, limit in (("job_name", 100), ("objective", 8000), ("role", 2000), ("context", 16000)):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > limit or (name != "context" and not value.strip()):
                raise ValueError("invalid " + name)
        if type(self.max_steps) is not int or not 1 <= self.max_steps <= 10000:
            raise ValueError("invalid max_steps")
        if type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 86400:
            raise ValueError("invalid timeout_seconds")
        for name in ("requested_tools", "lesson_keys"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or len(values) > 64:
                raise ValueError("invalid " + name)
            for value in values: ident(value)
            object.__setattr__(self, name, tuple(dict.fromkeys(values)))
        if not isinstance(self.copy_run, dict) or set(self.copy_run) - {"run_id", "parent_run_id", "root_run_id", "resume_of_run_id"}:
            raise ValueError("invalid copy_run")
        for value in self.copy_run.values(): ident(value)
        object.__setattr__(self, "copy_run", dict(self.copy_run))

def build_spec(assignment, lessons=()):
    instance = str(uuid.uuid4())
    return {"schema_version": 1, "instance_id": instance,
            "display_name": assignment.job_name + " / " + instance,
            **asdict(assignment), "lessons": list(lessons)}

class HostAdapter(Protocol):
    """Host must sandbox tools, enforce deadlines and attest checks independently."""
    def start(self, spec: dict) -> None: ...
    def cancel(self, instance_id: str) -> None: ...
    def dispose_context(self, instance_id: str) -> None: ...

class Store:
    """Single SQLite journal. Immutable rows; not a tamper-proof security boundary."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, instance_id TEXT NOT NULL, assignment_id TEXT NOT NULL, project_id TEXT NOT NULL, type TEXT NOT NULL, timestamp REAL NOT NULL, payload TEXT NOT NULL, schema_version INTEGER NOT NULL CHECK(schema_version=1))")
        for action in ("UPDATE", "DELETE"):
            self.db.execute(f"CREATE TRIGGER IF NOT EXISTS forbid_{action} BEFORE {action} ON events BEGIN SELECT RAISE(ABORT, 'append only'); END")
        if self.db.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
            raise ValueError("unsupported database schema")
        self.db.execute("PRAGMA user_version=1")

    def close(self): self.db.close()

    def events(self, instance_id=None):
        cursor = self.db.execute("SELECT * FROM events" + (" WHERE instance_id=?" if instance_id else "") + " ORDER BY sequence", (instance_id,) if instance_id else ())
        names = [col[0] for col in cursor.description]
        result = [dict(zip(names, row)) for row in cursor]
        for event in result: event["payload"] = json.loads(event["payload"])
        return result

    def append(self, spec, kind, payload, now):
        eid = str(uuid.uuid4())
        encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
        if len(encoded.encode()) > 65536: raise ValueError("event exceeds 64 KiB")
        self.db.execute("INSERT INTO events(event_id,instance_id,assignment_id,project_id,type,timestamp,payload,schema_version) VALUES(?,?,?,?,?,?,?,1)", (eid,spec["instance_id"],spec["assignment_id"],spec["project_id"],kind,now,encoded))
        return eid

    def lessons(self, project_id, keys, now, limit=8, configuration_hash=""):
        if type(limit) is not int or not 0 <= limit <= 32: raise ValueError("invalid limit")
        invalid = {e["payload"]["verification_event_id"] for e in self.events() if e["type"] == "verification_revoked"}
        revoked = {e["payload"]["lesson_id"] for e in self.events() if e["type"] == "lesson_revoked"}
        return [dict(e["payload"], event_id=e["event_id"], source_instance_id=e["instance_id"], selection_reason="exact project/key/configuration; current verification and expiry") for e in reversed(self.events()) if e["type"] == "lesson_validated" and e["project_id"] == project_id and e["payload"].get("configuration_hash", "") == configuration_hash and e["payload"]["key"] in keys and e["payload"]["expires_at"] > now and e["payload"]["lesson_id"] not in revoked and e["payload"]["verification_event_id"] not in invalid][:limit]

    def graph(self):
        nodes, edges = {}, []
        for e in self.events():
            instance = "instance:" + e["instance_id"]
            assignment = "assignment:" + e["project_id"] + ":" + e["assignment_id"]
            for key, kind in ((instance,"instance"),(assignment,"assignment"),(e["event_id"],"event")):
                nodes[key] = {"id": key, "kind": kind}
            edges.extend([{"source":instance,"target":assignment,"type":"assigned_to"},{"source":e["event_id"],"target":instance,"type":"records"}])
            if e["type"] == "allocated":
                for role, run in e["payload"]["copy_run"].items():
                    key = "copy_run:" + run
                    nodes[key] = {"id":key,"kind":"copy_run"}
                    edges.append({"source":instance,"target":key,"type":role})
            if e["type"] == "lesson_validated":
                edges.append({"source":e["event_id"],"target":e["payload"]["verification_event_id"],"type":"supported_by"})
        return {"schema_version":1,"nodes":list(nodes.values()),"edges":edges,"events":self.events()}

    def export_structure(self, instance_id, *, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000: raise ValueError("invalid export limit")
        events = self.events(instance_id)
        fields = ("schema_version","sequence","event_id","instance_id","assignment_id","project_id","type","timestamp")
        return {"schema_version":1,"events":[{k:e[k] for k in fields} for e in events[:limit]],
                "truncated":len(events)>limit,"total_events":len(events),
                "copy_run":events[0]["payload"].get("copy_run",{}) if events else {},
                "identity":{k:events[0]["payload"].get(k, "") for k in ("chat_id","task_id","template_id","configuration_hash","assignment_digest")} if events else {},
                "state":next((e["type"] for e in reversed(events) if e["type"] in TERMINAL | {"allocated","running","retired"}),"missing"),
                "omissions":["payloads","context","objective","messages","artifact_references","lesson_text"],
                "verification_count":sum(e["type"]=="verification" for e in events)}

class Lifecycle:
    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock
        self.contexts = {}

    def _load(self, instance):
        events = self.store.events(instance)
        if not events: raise KeyError(instance)
        spec = dict(events[0]["payload"], instance_id=instance, assignment_id=events[0]["assignment_id"], project_id=events[0]["project_id"])
        states = [e["type"] for e in events if e["type"] in TERMINAL | {"allocated","running","retired"}]
        return spec, states[-1], events

    def allocate(self, assignment, *, operation_id=None):
        digest = hashlib.sha256(json.dumps(asdict(assignment), sort_keys=True).encode()).hexdigest()
        if operation_id is not None:
            ident(operation_id)
            prior = next((e for e in self.store.events() if e["type"]=="allocated" and e["project_id"]==assignment.project_id and e["payload"].get("operation_id")==operation_id),None)
            if prior:
                if prior["payload"]["assignment_digest"]!=digest: raise ValueError("allocation identity conflict")
                instance=prior["instance_id"]
                if instance not in self.contexts: raise ValueError("allocation already exists; reconcile instance " + instance + "; private context cannot replay")
                return dict(self.contexts[instance])
        spec = build_spec(assignment, self.store.lessons(assignment.project_id, assignment.lesson_keys, self.clock(), configuration_hash=assignment.configuration_hash))
        durable = {k:v for k,v in spec.items() if k not in {"context","objective"}}
        durable["assignment_digest"] = digest
        if operation_id is not None: durable["operation_id"] = operation_id
        self.store.append(spec,"allocated",durable,self.clock())
        self.contexts[spec["instance_id"]] = spec
        return spec

    def transition(self, instance, state, *, summary="", evidence=(), operation_id=None):
        # Serialize read/check/write across controllers sharing this database.
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            spec, current, events = self._load(instance)
            payload = {"summary":summary,"evidence":list(evidence)}
            if operation_id is not None:
                ident(operation_id)
                payload["operation_id"] = operation_id
                prior = next((e for e in events if e["payload"].get("operation_id")==operation_id), None)
                if prior:
                    if prior["type"]!=state or prior["payload"]!=payload: raise ValueError("operation identity conflict")
                    self.store.db.execute("COMMIT")
                    return prior["event_id"]
            allowed = {"allocated":{"running","cancelled","failed"}, "running":TERMINAL}
            if state not in allowed.get(current,set()): raise ValueError("invalid lifecycle transition")
            if state == "running" and instance not in self.contexts:
                raise ValueError("recovered allocation cannot replay private context; allocate a new instance")
            if not isinstance(summary,str) or len(summary)>8000: raise ValueError("invalid summary")
            evidence = payload["evidence"]
            for item in evidence:
                if not isinstance(item,dict) or set(item) != {"ref","sha256"} or not isinstance(item["ref"],str) or len(item["ref"])>1000 or not isinstance(item["sha256"],str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]): raise ValueError("invalid evidence")
            eid = self.store.append(spec,state,payload,self.clock())
            self.store.db.execute("COMMIT")
            return eid
        except BaseException:
            self.store.db.execute("ROLLBACK")
            raise

    def step(self, instance):
        spec, state, events = self._load(instance)
        if state != "running": raise ValueError("not running")
        start = next(e["timestamp"] for e in events if e["type"] == "running")
        if self.clock() - start >= spec["timeout_seconds"]:
            self.transition(instance,"timed_out",summary="Host checkpoint deadline reached")
            return False
        if sum(e["type"] == "step" for e in events) >= spec["max_steps"]:
            self.transition(instance,"failed",summary="Step budget exhausted")
            return False
        self.store.append(spec,"step",{},self.clock())
        return True

    def verify(self, instance, *, passed, verifier, evidence_event_id, check, operation_id=None):
        spec, state, events = self._load(instance)
        payload={"passed":passed,"verifier":verifier,"evidence_event_id":evidence_event_id,"check":check}
        if operation_id is not None:
            ident(operation_id); payload["operation_id"]=operation_id
            prior=next((e for e in events if e["payload"].get("operation_id")==operation_id),None)
            if prior:
                if prior["type"]!="verification" or prior["payload"]!=payload: raise ValueError("verification identity conflict")
                return prior["event_id"]
        if state not in TERMINAL: raise ValueError("verify terminal outcome before retirement")
        ident(verifier)
        source = next((e for e in events if e["event_id"] == evidence_event_id and e["type"] in TERMINAL),None)
        if type(passed) is not bool or not source or not source["payload"]["evidence"] or not isinstance(check,str) or not check.strip() or len(check)>2000:
            raise ValueError("missing bound evidence or check")
        return self.store.append(spec,"verification",payload,self.clock())

    def revoke_verification(self, instance, verification_event_id, *, reason):
        spec, _, events = self._load(instance)
        if not any(e["type"]=="verification" and e["event_id"]==verification_event_id for e in events): raise ValueError("unknown verification")
        if not isinstance(reason,str) or not reason.strip() or len(reason)>2000: raise ValueError("invalid revocation reason")
        return self.store.append(spec,"verification_revoked",{"verification_event_id":verification_event_id,"reason":reason},self.clock())

    def add_lesson(self, instance, *, key, text, verification_event_id, expires_at):
        spec, state, events = self._load(instance)
        ident(key)
        verification = next((e for e in events if e["event_id"] == verification_event_id and e["type"] == "verification"),None)
        if not verification or not verification["payload"]["passed"] or any(e["type"]=="verification_revoked" and e["payload"]["verification_event_id"]==verification_event_id for e in events): raise ValueError("lesson requires passed, non-revoked verification")
        if not isinstance(text,str) or not text.strip() or len(text)>2000 or type(expires_at) not in (int,float) or not math.isfinite(expires_at) or not self.clock()<expires_at<=self.clock()+2592000:
            raise ValueError("invalid lesson or expiry (maximum 30 days)")
        lesson_id = str(uuid.uuid4())
        self.store.append(spec,"lesson_validated",{"lesson_id":lesson_id,"configuration_hash":spec.get("configuration_hash", ""),"key":key,"text":text,"verification_event_id":verification_event_id,"expires_at":expires_at},self.clock())
        return lesson_id

    def revoke_lesson(self, instance, lesson_id):
        spec, _, events = self._load(instance)
        if not any(e["type"]=="lesson_validated" and e["payload"]["lesson_id"]==lesson_id for e in events): raise ValueError("unknown lesson")
        self.store.append(spec,"lesson_revoked",{"lesson_id":lesson_id},self.clock())

    def retire(self, instance, *, retention_ack):
        ident(retention_ack)
        spec, state, events = self._load(instance)
        if state == "retired":
            prior = next(e for e in events if e["type"]=="retired")
            if prior["payload"]["retention_ack"] != retention_ack: raise ValueError("retirement ACK conflict")
            self.contexts.pop(instance,None)
            return prior["event_id"]
        if state not in TERMINAL: raise ValueError("persist terminal outcome before retirement")
        eid = self.store.append(spec,"retired",{"host_context_disposal_required":True,"retention_ack":retention_ack},self.clock())
        self.contexts.pop(instance,None)
        return eid
