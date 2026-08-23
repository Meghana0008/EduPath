from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.status_agent import ApplicationStatusAgent, VALID_TRANSITIONS
from app.models import Application, Notification, Opportunity
from app.services import agent_logger
from app.utils.ids import new_id


STATUS_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "DISBURSED",
        [
            r"\bdisburs",
            r"\bcredited\b",
            r"\btransferred to (?:your )?bank\b",
            r"\bdbt\b.*\bsuccess",
            r"\bamount (?:has been )?credited\b",
        ],
    ),
    (
        "APPROVED",
        [
            r"\bapproved\b",
            r"\bselected\b",
            r"\bawarded\b",
            r"\bsanctioned\b",
            r"\bcongratulations\b.*\bscholarship\b",
            r"\boffer (?:of )?(?:award|scholarship)\b",
        ],
    ),
    (
        "REJECTED",
        [
            r"\brejected\b",
            r"\bnot selected\b",
            r"\bunsuccessful\b",
            r"\bregret to inform\b",
            r"\bapplication.*(?:closed|denied)\b",
        ],
    ),
    (
        "INTERVIEW",
        [r"\binterview\b", r"\bvirtual meeting\b", r"\bschedule.*discussion\b"],
    ),
    (
        "DOCUMENT_VERIFICATION",
        [
            r"\bdocument verification\b",
            r"\bdefective application\b",
            r"\bre-?upload\b",
            r"\badditional documents?\b",
            r"\bverification pending\b",
        ],
    ),
    (
        "UNDER_REVIEW",
        [
            r"\bunder review\b",
            r"\bbeing (?:processed|reviewed)\b",
            r"\bin process\b",
            r"\bapplication received and (?:is )?under\b",
        ],
    ),
    (
        "SUBMITTED",
        [
            r"\bapplication (?:has been )?submitted\b",
            r"\bsuccessfully submitted\b",
            r"\bapplication received\b",
            r"\backnowledg(?:e)?ment\b",
        ],
    ),
]


class EmailTrackingAgent:
    """Agent that watches ONLY emails related to the student's tracked applications."""

    TRACKABLE_STATUSES = {
        "DRAFT",
        "SUBMITTED",
        "UNDER_REVIEW",
        "DOCUMENT_VERIFICATION",
        "INTERVIEW",
        "APPROVED",
        "REJECTED",
        "DISBURSED",
        "NOT_STARTED",
    }

    def watched_applications(self, db: Session, student_id: str) -> list[dict[str, Any]]:
        apps = db.query(Application).filter(Application.student_id == student_id).all()
        watched = []
        for app in apps:
            # Only track schemes the student actually started in EduPath
            if app.status == "NOT_STARTED":
                continue
            opp = db.query(Opportunity).filter(Opportunity.id == app.opportunity_id).first()
            if not opp:
                continue
            watched.append(
                {
                    "application": app,
                    "opportunity": opp,
                    "keywords": self._keywords_for_opportunity(opp),
                }
            )
        return watched

    def _keywords_for_opportunity(self, opp: Opportunity) -> list[str]:
        stop = {
            "for",
            "the",
            "and",
            "of",
            "to",
            "in",
            "on",
            "a",
            "an",
            "scheme",
            "scholarship",
            "students",
            "student",
            "india",
            "with",
            "from",
        }
        tokens: list[str] = []
        for raw in [opp.title or "", opp.provider or "", opp.source_name or ""]:
            for tok in re.findall(r"[A-Za-z0-9]{4,}", raw):
                low = tok.lower()
                if low not in stop and low not in tokens:
                    tokens.append(low)
        # Keep strongest/specific tokens first
        return tokens[:8]

    def classify_email(self, subject: str, body: str) -> dict[str, Any]:
        text = f"{subject}\n{body}".lower()
        for status, patterns in STATUS_PATTERNS:
            for pat in patterns:
                if re.search(pat, text, flags=re.IGNORECASE):
                    return {
                        "proposed_status": status,
                        "confidence": 0.82 if status in {"APPROVED", "REJECTED", "DISBURSED"} else 0.7,
                        "matched_pattern": pat,
                    }
        return {"proposed_status": None, "confidence": 0.0, "matched_pattern": None}

    def match_application(
        self, db: Session, student_id: str, subject: str, body: str
    ) -> Optional[Application]:
        watched = self.watched_applications(db, student_id)
        if not watched:
            return None
        blob = f"{subject}\n{body}".lower()
        best: Optional[Application] = None
        best_score = 0
        for item in watched:
            app = item["application"]
            opp = item["opportunity"]
            keywords = item["keywords"]
            score = 0
            title = (opp.title or "").lower()
            if title and title[:24] in blob:
                score += 6
            for token in keywords:
                if token in blob:
                    score += 3 if len(token) >= 6 else 2
            provider = (opp.provider or "").lower()
            if provider and provider in blob:
                score += 3
            if "nsp" in blob and "nsp" in (opp.source_name or "").lower():
                score += 2
            if "scholarships.gov.in" in blob and "nsp" in (opp.source_name or "").lower():
                score += 2
            if score > best_score:
                best_score = score
                best = app
        # Must clearly relate to a tracked application — ignore unrelated scholarship spam
        return best if best_score >= 4 else None

    def ingest_email_text(
        self,
        db: Session,
        student_id: str,
        *,
        subject: str,
        body: str,
        from_address: str = "",
        auto_apply: bool = False,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        run = agent_logger.start_agent_run(
            db,
            agent_name="email_tracking_agent",
            run_type="email_ingest",
            student_id=student_id,
            input_summary=subject[:180],
        )
        classification = self.classify_email(subject, body)
        app = self.match_application(db, student_id, subject, body)
        agent_logger.append_step(
            db,
            run,
            f"Classified as {classification['proposed_status'] or 'NO_SIGNAL'} "
            f"(confidence {classification['confidence']})",
        )

        if not classification["proposed_status"]:
            agent_logger.complete_agent_run(
                db, run, status="completed", output_summary="No status signal found in email"
            )
            return {
                "ok": True,
                "proposal": None,
                "reason": "No clear scholarship status signal found in this email.",
            }

        if not app:
            agent_logger.complete_agent_run(
                db, run, status="completed", output_summary="Signal found but no matching application"
            )
            return {
                "ok": True,
                "proposal": None,
                "reason": (
                    "Found a possible status update, but could not match it to one of your tracked applications. "
                    "Start an application in EduPath for that scheme first."
                ),
                "proposed_status": classification["proposed_status"],
            }

        proposal_id = new_id("eprop_")
        snippet = re.sub(r"\s+", " ", body)[:280]
        proposal = {
            "id": proposal_id,
            "application_id": app.id,
            "from_status": app.status,
            "proposed_status": classification["proposed_status"],
            "confidence": classification["confidence"],
            "subject": subject,
            "from_address": from_address,
            "snippet": snippet,
            "message_id": message_id or new_id("msg_"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }

        # Store proposal on application timeline metadata via notification
        ntf = Notification(
            id=new_id("ntf_"),
            student_id=student_id,
            type="EMAIL_STATUS_PROPOSAL",
            title=f"Email suggests: {classification['proposed_status']}",
            message=(
                f"From mail “{subject[:120]}”. "
                f"Proposed update for application {app.id}: {app.status} → {classification['proposed_status']}."
            ),
            priority="high" if classification["proposed_status"] in {"APPROVED", "REJECTED", "DISBURSED"} else "medium",
            dedupe_key=f"emailprop:{student_id}:{proposal['message_id']}:{classification['proposed_status']}",
            metadata_json={"proposal": proposal, "opportunity_id": app.opportunity_id},
        )
        existing = (
            db.query(Notification)
            .filter(Notification.dedupe_key == ntf.dedupe_key)
            .first()
        )
        if existing:
            agent_logger.complete_agent_run(db, run, output_summary="Duplicate email proposal skipped")
            return {"ok": True, "proposal": existing.metadata_json.get("proposal"), "duplicate": True}

        db.add(ntf)

        # Agent mode: auto-apply progress updates for matched applications.
        # Keep APPROVED/REJECTED/DISBURSED as proposals unless auto_apply is enabled.
        sensitive = classification["proposed_status"] in {"APPROVED", "REJECTED", "DISBURSED"}
        should_auto = (auto_apply and classification["confidence"] >= 0.7) or (
            not sensitive and classification["confidence"] >= 0.7
        )
        applied = None
        if should_auto:
            applied = self.apply_proposal(db, student_id, proposal, confirm=True)
            proposal["status"] = "applied" if applied.get("ok") else "pending"
            ntf.metadata_json = {**(ntf.metadata_json or {}), "proposal": proposal}
            ntf.read = bool(applied and applied.get("changed"))
            ntf.type = "APPLICATION_UPDATE" if applied and applied.get("changed") else ntf.type
            if applied and applied.get("changed"):
                ntf.title = f"Agent updated application → {classification['proposed_status']}"
                ntf.message = (
                    f"Matched email “{subject[:100]}” to your tracked application and updated status."
                )
            db.add(ntf)

        db.commit()
        agent_logger.complete_agent_run(
            db,
            run,
            output_summary=(
                f"{'Applied' if applied and applied.get('changed') else 'Proposed'} "
                f"{classification['proposed_status']} for watched application {app.id}"
            ),
            metadata={
                "proposal_id": proposal_id,
                "auto_applied": bool(applied and applied.get("changed")),
                "watched_only": True,
            },
        )
        return {"ok": True, "proposal": proposal, "auto_applied": applied}

    def apply_proposal(
        self, db: Session, student_id: str, proposal: dict[str, Any], *, confirm: bool = False
    ) -> dict[str, Any]:
        app = (
            db.query(Application)
            .filter(
                Application.id == proposal["application_id"],
                Application.student_id == student_id,
            )
            .first()
        )
        if not app:
            return {"ok": False, "error": "Application not found"}

        target = proposal["proposed_status"].upper()
        if app.status == target:
            return {"ok": True, "changed": False, "application": app}

        if not confirm:
            return {
                "ok": False,
                "requires_confirmation": True,
                "confirmation_prompt": (
                    f"Email evidence suggests updating this application to {target}. "
                    "Confirm to apply this status change."
                ),
            }

        # Walk allowed transitions when possible; otherwise allow email-confirmed jump
        path = self._transition_path(app.status, target)
        status_agent = ApplicationStatusAgent()
        if path:
            current = app
            for step in path:
                result = status_agent.update_status(
                    db,
                    current,
                    step,
                    confirm=True,
                    notes=f"Auto-tracked from email: {proposal.get('subject', '')[:160]}",
                )
                if not result.get("ok"):
                    return result
                current = result["application"]
            # annotate last timeline item with email evidence
            timeline = list(current.timeline or [])
            if timeline:
                timeline[-1]["source"] = "email"
                timeline[-1]["email_subject"] = proposal.get("subject")
                timeline[-1]["email_snippet"] = proposal.get("snippet")
                current.timeline = timeline
                db.add(current)
                db.commit()
                db.refresh(current)
            return {"ok": True, "changed": True, "application": current}

        # Direct jump for email-confirmed updates outside simple path
        timeline = list(app.timeline or [])
        timeline.append(
            {
                "status": target,
                "at": datetime.now(timezone.utc).isoformat(),
                "note": f"Updated from email: {proposal.get('subject', '')[:160]}",
                "source": "email",
                "email_subject": proposal.get("subject"),
                "email_snippet": proposal.get("snippet"),
            }
        )
        app.status = target
        app.timeline = timeline
        app.last_status_update = datetime.now(timezone.utc)
        if target == "SUBMITTED" and not app.submitted_at:
            app.submitted_at = datetime.now(timezone.utc)
        db.add(app)
        db.add(
            Notification(
                id=new_id("ntf_"),
                student_id=student_id,
                type="APPLICATION_UPDATE",
                title=f"Status updated from email → {target}",
                message=f"EduPath applied an email-detected update to {target}.",
                priority="high",
                dedupe_key=f"emailapply:{app.id}:{target}:{proposal.get('message_id')}",
                metadata_json={"application_id": app.id, "status": target, "source": "email"},
            )
        )
        db.commit()
        db.refresh(app)
        return {"ok": True, "changed": True, "application": app}

    def _transition_path(self, start: str, target: str) -> list[str]:
        if start == target:
            return []
        # BFS over VALID_TRANSITIONS
        queue = [(start, [])]
        seen = {start}
        while queue:
            node, path = queue.pop(0)
            for nxt in VALID_TRANSITIONS.get(node, set()):
                if nxt in seen:
                    continue
                new_path = path + [nxt]
                if nxt == target:
                    return new_path
                seen.add(nxt)
                queue.append((nxt, new_path))
        return []

    def run_watch_sync(
        self,
        db: Session,
        student_id: str,
        *,
        email_address: str = "",
        app_password: str = "",
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        auto_apply: bool = True,
        access_token: str | None = None,
        auth_mode: str = "imap",
    ) -> dict[str, Any]:
        """Full agent loop: watch only mails for applications the student started."""
        run = agent_logger.start_agent_run(
            db,
            agent_name="email_tracking_agent",
            run_type="application_email_watch",
            student_id=student_id,
            input_summary="Watch inbox for tracked application updates only",
        )
        watched = self.watched_applications(db, student_id)
        if not watched:
            agent_logger.append_step(
                db, run, "No tracked applications yet — start an application first", status="warning"
            )
            agent_logger.complete_agent_run(
                db, run, output_summary="Nothing to watch: no started applications"
            )
            return {
                "ok": True,
                "watched_applications": 0,
                "scanned": 0,
                "matched": 0,
                "proposals": [],
                "message": "Start an application in EduPath first. The agent only tracks emails for schemes you applied to.",
            }

        watch_terms = sorted({kw for item in watched for kw in item["keywords"]})[:12]
        agent_logger.append_step(
            db,
            run,
            f"Watching {len(watched)} application(s) with terms: {', '.join(watch_terms[:6])}",
        )

        if auth_mode == "gmail_oauth" and access_token:
            from app.services.gmail_oauth import fetch_gmail_messages

            messages = fetch_gmail_messages(
                access_token,
                watch_terms=watch_terms,
                limit=40,
            )
            agent_logger.append_step(db, run, f"Fetched {len(messages)} Gmail message(s) via Google login")
        else:
            messages = self.fetch_imap_messages(
                email_address=email_address,
                app_password=app_password,
                imap_host=imap_host,
                imap_port=imap_port,
                watch_terms=watch_terms,
                limit=40,
            )
            agent_logger.append_step(db, run, f"Fetched {len(messages)} candidate email(s) for watched schemes")

        proposals = []
        matched = 0
        ignored = 0
        for msg in messages:
            result = self.ingest_email_text(
                db,
                student_id,
                subject=msg.get("subject") or "",
                body=msg.get("body") or "",
                from_address=msg.get("from_address") or "",
                auto_apply=auto_apply,
                message_id=msg.get("message_id"),
            )
            if result.get("proposal"):
                matched += 1
                proposals.append(result["proposal"])
            else:
                ignored += 1

        agent_logger.append_step(
            db,
            run,
            f"Matched {matched} email(s) to your applications; ignored {ignored} unrelated",
        )
        agent_logger.complete_agent_run(
            db,
            run,
            output_summary=f"Watched {len(watched)} apps · matched {matched} emails",
            metadata={
                "watched_applications": len(watched),
                "scanned": len(messages),
                "matched": matched,
                "ignored": ignored,
                "auth_mode": auth_mode,
            },
        )
        return {
            "ok": True,
            "watched_applications": len(watched),
            "watch_terms": watch_terms,
            "scanned": len(messages),
            "matched": matched,
            "ignored": ignored,
            "proposals": proposals,
            "message": (
                f"Agent watched {len(watched)} application(s) and matched {matched} related email(s)."
            ),
        }

    def fetch_imap_messages(
        self,
        *,
        email_address: str,
        app_password: str,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        watch_terms: list[str] | None = None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        """Fetch inbox messages, preferring searches tied to watched application keywords."""
        messages: list[dict[str, Any]] = []
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        try:
            mail.login(email_address, app_password)
            mail.select("INBOX")
            id_set: set[bytes] = set()

            terms = [t for t in (watch_terms or []) if t]
            # Build targeted IMAP subject searches from the student's applications
            searches = []
            for term in terms[:8]:
                safe = re.sub(r"[^A-Za-z0-9 \-_]", "", term)[:40]
                if safe:
                    searches.append(f'(SUBJECT "{safe}")')
            # Always include common official portals only as secondary filters
            searches.extend(
                [
                    '(OR SUBJECT "NSP" SUBJECT "National Scholarship")',
                    '(OR FROM "scholarships.gov.in" FROM "aicte")',
                ]
            )

            for criteria in searches:
                typ, data = mail.search(None, criteria)
                if typ == "OK" and data and data[0]:
                    id_set.update(data[0].split())

            if not id_set:
                # Fallback: recent mail only (still filtered later by application match)
                typ, data = mail.search(None, "ALL")
                if typ == "OK" and data and data[0]:
                    id_set.update(data[0].split()[-30:])

            ids = sorted(id_set, key=lambda x: int(x))[-limit:]
            for msg_id in ids:
                typ, msg_data = mail.fetch(msg_id, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                parsed = email.message_from_bytes(raw)
                subject = _decode_mime(parsed.get("Subject", ""))
                from_addr = parsed.get("From", "")
                body = _extract_body(parsed)
                messages.append(
                    {
                        "message_id": parsed.get("Message-ID") or msg_id.decode(),
                        "subject": subject,
                        "from_address": from_addr,
                        "body": body,
                    }
                )
        finally:
            try:
                mail.logout()
            except Exception:  # noqa: BLE001
                pass
        return messages


def _decode_mime(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(chunk)
    return "".join(out)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", " ", text)
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
