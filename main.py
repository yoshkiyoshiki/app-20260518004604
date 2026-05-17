import streamlit as st
import datetime
import json
import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class Phase(Enum):
    ACTIVE = "Active"
    PAUSED = "Paused"
    ARCHIVED = "Archived"

class Urgency(Enum):
    URGENT = "🔴 Urgent"
    IMPORTANT = "🟡 Important"
    FYI = "🔵 FYI"
    NOISE = "⚪ Noise"

if "projects" not in st.session_state:
    st.session_state.projects = {}
if "current_project" not in st.session_state:
    st.session_state.current_project = None
if "messages" not in st.session_state:
    st.session_state.messages = {}
if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = {}
if "focus_mode" not in st.session_state:
    st.session_state.focus_mode = False
if "user_name" not in st.session_state:
    st.session_state.user_name = "You"
if "notifications" not in st.session_state:
    st.session_state.notifications = []

def create_project(name, description, phase="Active"):
    pid = str(uuid.uuid4())[:8]
    st.session_state.projects[pid] = {"name": name, "description": description, "phase": phase, "created": datetime.datetime.now().isoformat(), "members": ["You"], "pins": []}
    st.session_state.messages[pid] = []
    st.session_state.knowledge_base[pid] = {"decisions": [], "todos": [], "qa": [], "insights": []}
    return pid

def extract_knowledge(messages, pid):
    kb = st.session_state.knowledge_base[pid]
    for msg in messages:
        text = msg["text"].lower()
        if any(kw in text for kw in ["decided", "decision", "決定", "we'll go with", "let's go with", "agreed"]):
            entry = {"text": msg["text"], "author": msg["author"], "time": msg["time"], "status": "pending_review"}
            if entry not in kb["decisions"]:
                kb["decisions"].append(entry)
        if any(kw in text for kw in ["todo", "action item", "task:", "need to", "should do", "やること", "タスク"]):
            entry = {"text": msg["text"], "author": msg["author"], "time": msg["time"], "done": False}
            if entry not in kb["todos"]:
                kb["todos"].append(entry)
        if "?" in msg["text"] or "？" in msg["text"]:
            entry = {"question": msg["text"], "author": msg["author"], "time": msg["time"], "answer": None}
            if entry not in kb["qa"]:
                kb["qa"].append(entry)
        if any(kw in text for kw in ["insight", "important", "key point", "注目", "重要"]):
            entry = {"text": msg["text"], "author": msg["author"], "time": msg["time"]}
            if entry not in kb["insights"]:
                kb["insights"].append(entry)

def classify_urgency(text):
    t = text.lower()
    if any(kw in t for kw in ["urgent", "asap", "emergency", "緊急", "至急", "blocker", "down", "broken"]):
        return Urgency.URGENT
    if any(kw in t for kw in ["important", "重要", "please review", "need", "required", "deadline"]):
        return Urgency.IMPORTANT
    if any(kw in t for kw in ["fyi", "参考", "btw", "ちなみに", "note"]):
        return Urgency.FYI
    return Urgency.NOISE

def generate_summary(messages):
    if not messages:
        return "No messages to summarize."
    total = len(messages)
    authors = list(set(m["author"] for m in messages))
    topics = []
    for m in messages:
        if "?" in m["text"]:
            topics.append("Questions raised")
        if any(kw in m["text"].lower() for kw in ["decided", "decision"]):
            topics.append("Decisions made")
        if any(kw in m["text"].lower() for kw in ["todo", "task"]):
            topics.append("Action items identified")
    topics = list(set(topics)) if topics else ["General discussion"]
    summary = f"**Summary of {total} messages**\n\n"
    summary += f"- **Participants**: {', '.join(authors)}\n"
    summary += f"- **Period**: {messages[0]['time'][:10]} to {messages[-1]['time'][:10]}\n"
    summary += f"- **Topics**: {', '.join(topics)}\n\n"
    summary += "**Recent highlights:**\n"
    for m in messages[-3:]:
        summary += f"- [{m['author']}] {m['text'][:80]}...\n" if len(m["text"]) > 80 else f"- [{m['author']}] {m['text']}\n"
    return summary

def search_messages(query, project_id=None):
    results = []
    q = query.lower()
    targets = {project_id: st.session_state.messages.get(project_id, [])} if project_id else st.session_state.messages
    for pid, msgs in targets.items():
        pname = st.session_state.projects.get(pid, {}).get("name", "Unknown")
        for m in msgs:
            if q in m["text"].lower() or q in m["author"].lower():
                results.append({**m, "project": pname, "pid": pid})
    return results

st.set_page_config(page_title="Flowspace", page_icon="🌊", layout="wide")

st.markdown("""<style>
.stApp {background-color: #0e1117;}
div[data-testid="stSidebar"] {background-color: #161b22;}
.focus-badge {background: #238636; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;}
.urgent-badge {background: #da3633; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🌊 Flowspace")
    st.caption("Focus-first communication")
    st.divider()
    focus_col1, focus_col2 = st.columns([3, 1])
    with focus_col1:
        st.session_state.focus_mode = st.toggle("🎯 Focus Mode", st.session_state.focus_mode)
    if st.session_state.focus_mode:
        with focus_col2:
            st.markdown('<span class="focus-badge">ON</span>', unsafe_allow_html=True)
    st.divider()
    st.markdown("### Projects")
    with st.expander("➕ New Project"):
        new_name = st.text_input("Project Name", key="new_proj_name")
        new_desc = st.text_area("Description", key="new_proj_desc", height=68)
        new_phase = st.selectbox("Phase", [p.value for p in Phase], key="new_proj_phase")
        if st.button("Create Project") and new_name:
            pid = create_project(new_name, new_desc, new_phase)
            st.session_state.current_project = pid
            st.rerun()
    for pid, proj in st.session_state.projects.items():
        phase_icon = {"Active": "🟢", "Paused": "⏸️", "Archived": "📦"}.get(proj["phase"], "")
        unread = len([m for m in st.session_state.messages.get(pid, []) if not m.get("read", False)])
        label = f"{phase_icon} {proj['name']}"
        if unread > 0:
            label += f" ({unread})"
        if st.button(label, key=f"proj_{pid}", use_container_width=True):
            st.session_state.current_project = pid
            st.rerun()
    st.divider()
    urgent_notifs = [n for n in st.session_state.notifications if "Urgent" in n.get("urgency", "")]
    if urgent_notifs:
        st.markdown(f'<span class="urgent-badge">🔔 {len(urgent_notifs)} urgent</span>', unsafe_allow_html=True)
        for n in urgent_notifs[-3:]:
            st.caption(f"{n['text'][:50]}")

if not st.session_state.projects:
    st.markdown("# 🌊 Welcome to Flowspace")
    st.markdown("### Focus-first, AI-native communication for teams")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 📁 Project Hub")
        st.markdown("Organize conversations by project, not channels. Every message has context.")
    with col2:
        st.markdown("#### 🧠 AI Knowledge Engine")
        st.markdown("Decisions, TODOs, and insights auto-extracted from conversations.")
    with col3:
        st.markdown("#### 🎯 Focus Guard")
        st.markdown("Smart notifications that respect your deep work time.")
    st.info("👈 Create your first project from the sidebar to get started!")
    if st.button("🚀 Create Demo Project"):
        pid = create_project("Product Launch v2.0", "Q1 product launch planning and coordination", "Active")
        demo_msgs = [
            {"id": str(uuid.uuid4())[:8], "author": "Alice", "text": "We decided to go with the new API design for v2. Decision: RESTful endpoints with GraphQL for complex queries.", "time": (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat(), "read": True, "reactions": {"👍": 3}},
            {"id": str(uuid.uuid4())[:8], "author": "Bob", "text": "TODO: Update the authentication middleware to support OAuth2.0 by next Friday.", "time": (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat(), "read": True, "reactions": {}},
            {"id": str(uuid.uuid4())[:8], "author": "Carol", "text": "What's the timeline for the frontend redesign? We need to coordinate with marketing.", "time": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(), "read": False, "reactions": {"🤔": 1}},
            {"id": str(uuid.uuid4())[:8], "author": "Alice", "text": "Important: The launch date is confirmed for March 15th. All teams need to align.", "time": datetime.datetime.now().isoformat(), "read": False, "reactions": {"🎯": 2}},
        ]
        st.session_state.messages[pid] = demo_msgs
        extract_knowledge(demo_msgs, pid)
        st.session_state.current_project = pid
        st.rerun()
elif st.session_state.current_project is None:
    st.info("👈 Select a project from the sidebar")
else:
    pid = st.session_state.current_project
    proj = st.session_state.projects[pid]
    header_col1, header_col2, header_col3 = st.columns([4, 1, 1])
    with header_col1:
        st.markdown(f"# {proj['name']}")
        st.caption(proj["description"])
    with header_col2:
        new_phase = st.selectbox("Phase", [p.value for p in Phase], index=[p.value for p in Phase].index(proj["phase"]), key="phase_sel", label_visibility="collapsed")
        if new_phase != proj["phase"]:
            proj["phase"] = new_phase
            st.rerun()
    with header_col3:
        st.caption(f"👥 {len(proj['members'])} members")
    tab_chat, tab_knowledge, tab_search, tab_summary, tab_settings = st.tabs(["💬 Chat", "🧠 Knowledge Base", "🔍 Search", "📋 Summary", "⚙️ Settings"])
    with tab_chat:
        msgs = st.session_state.messages.get(pid, [])
        chat_container = st.container(height=400)
        with chat_container:
            if not msgs:
                st.caption("No messages yet. Start the conversation!")
            for msg in msgs:
                urgency = classify_urgency(msg["text"])
                with st.chat_message("user" if msg["author"] == "You" else "assistant"):
                    col_a, col_b = st.columns([6, 1])
                    with col_a:
                        st.markdown(f"**{msg['author']}** · {msg['time'][:16].replace('T', ' ')}")
                        st.markdown(msg["text"])
                    with col_b:
                        st.caption(urgency.value)
                    if msg.get("reactions"):
                        reaction_str = " ".join(f"{emoji} {count}" for emoji, count in msg["reactions"].items())
                        st.caption(reaction_str)
                msg["read"] = True
        msg_col1, msg_col2 = st.columns([5, 1])
        with msg_col1:
            new_msg = st.chat_input("Type a message..." + (" (Focus Mode ON - async replies encouraged)" if st.session_state.focus_mode else ""))
        if new_msg:
            message = {"id": str(uuid.uuid4())[:8], "author": st.session_state.user_name, "text": new_msg, "time": datetime.datetime.now().isoformat(), "read": True, "reactions": {}}
            st.session_state.messages[pid].append(message)
            urgency = classify_urgency(new_msg)
            if urgency == Urgency.URGENT:
                st.session_state.notifications.append({"text": new_msg[:60], "urgency": urgency.value, "project": proj["name"], "time": datetime.datetime.now().isoformat()})
            extract_knowledge(st.session_state.messages[pid], pid)
            st.rerun()
    with tab_knowledge:
        kb = st.session_state.knowledge_base.get(pid, {"decisions": [], "todos": [], "qa": [], "insights": []})
        k_col1, k_col2 = st.columns(2)
        with k_col1:
            st.markdown("### ✅ Decisions")
            if not kb["decisions"]:
                st.caption("No decisions extracted yet.")
            for i, d in enumerate(kb["decisions"]):
                with st.container(border=True):
                    st.markdown(f"**{d['author']}** · {d['time'][:10]}")
                    st.markdown(d["text"])
                    status = d.get("status", "pending_review")
                    if status == "pending_review":
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Approve", key=f"approve_d_{pid}_{i}"):
                                d["status"] = "approved"
                                st.rerun()
                        with c2:
                            if st.button("❌ Reject", key=f"reject_d_{pid}_{i}"):
                                d["status"] = "rejected"
                                st.rerun()
                    else:
                        st.caption(f"Status: {status}")
            st.markdown("### 💡 Insights")
            if not kb["insights"]:
                st.caption("No insights extracted yet.")
            for ins in kb["insights"]:
                with st.container(border=True):
                    st.markdown(f"**{ins['author']}**: {ins['text']}")
        with k_col2:
            st.markdown("### 📝 TODOs")
            if not kb["todos"]:
                st.caption("No action items extracted yet.")
            for i, t in enumerate(kb["todos"]):
                done = st.checkbox(t["text"][:80], value=t["done"], key=f"todo_{pid}_{i}")
                if done != t["done"]:
                    t["done"] = done
            st.markdown("### ❓ Q&A")
            if not kb["qa"]:
                st.caption("No questions extracted yet.")
            for q in kb["qa"]:
                with st.container(border=True):
                    st.markdown(f"**Q ({q['author']}):** {q['question']}")
                    if q.get("answer"):
                        st.markdown(f"**A:** {q['answer']}")
                    else:
                        st.caption("Awaiting answer...")
    with tab_search:
        st.markdown("### 🔍 Semantic Search")
        search_query = st.text_input("Search across all messages...", placeholder="e.g., API redesign decision rationale")
        search_scope = st.radio("Scope", ["This Project", "All Projects"], horizontal=True)
        if search_query:
            scope_pid = pid if search_scope == "This Project" else None
            results = search_messages(search_query, scope_pid)
            if results:
                st.success(f"Found {len(results)} results")
                for r in results:
                    with st.container(border=True):
                        st.markdown(f"**{r['author']}** in *{r['project']}* · {r['time'][:16].replace('T', ' ')}")
                        highlighted = r["text"].replace(search_query, f"**{search_query}**")
                        st.markdown(highlighted)
            else:
                st.warning("No results found. Try different keywords.")
        st.markdown("### ⏳ Time Travel")
        travel_date = st.date_input("View project state as of:", datetime.date.today())
        if st.button("🕐 View State"):
            cutoff = datetime.datetime.combine(travel_date, datetime.time(23, 59, 59)).isoformat()
            historical = [m for m in st.session_state.messages.get(pid, []) if m["time"] <= cutoff]
            st.info(f"Project state as of {travel_date}: {len(historical)} messages")
            if historical:
                for m in historical[-5:]:
                    st.caption(f"[{m['author']}] {m['text'][:100]}")
    with tab_summary:
        st.markdown("### 📋 Conversation Summary")
        sum_col1, sum_col2 = st.columns(2)
        with sum_col1:
            start_date = st.date_input("From", datetime.date.today() - datetime.timedelta(days=7), key="sum_start")
        with sum_col2:
            end_date = st.date_input("To", datetime.date.today(), key="sum_end")
        if st.button("🤖 Generate Summary"):
            start_iso = datetime.datetime.combine(start_date, datetime.time(0, 0)).isoformat()
            end_iso = datetime.datetime.combine(end_date, datetime.time(23, 59, 59)).isoformat()
            period_msgs = [m for m in st.session_state.messages.get(pid, []) if start_iso <= m["time"] <= end_iso]
            summary = generate_summary(period_msgs)
            st.markdown(summary)
            kb = st.session_state.knowledge_base.get(pid, {})
            if kb.get("decisions"):
                st.markdown("**📌 Decisions in this period:**")
                for d in kb["decisions"]:
                    if start_iso <= d["time"] <= end_iso:
                        st.markdown(f"- {d['text'][:100]}")
            if kb.get("todos"):
                pending = [t for t in kb["todos"] if not t["done"]]
                if pending:
                    st.markdown(f"**📝 Open TODOs: {len(pending)}**")
                    for t in pending:
                        st.markdown(f"- {t['text'][:100]}")
    with tab_settings:
        st.markdown("### ⚙️ Project Settings")
        new_name = st.text_input("Project Name", value=proj["name"], key="edit_name")
        new_desc = st.text_area("Description", value=proj["description"], key="edit_desc")
        if st.button("Save Changes"):
            proj["name"] = new_name
            proj["description"] = new_desc
            st.success("Project updated!")
            st.rerun()
        st.markdown("### 👥 Members")
        new_member = st.text_input("Add member")
        if st.button("Add") and new_member:
            proj["members"].append(new_member)
            st.success(f"Added {new_member}")
            st.rerun()
        for m in proj["members"]:
            st.markdown(f"- {m}")
        st.divider()
        st.markdown("### 🔗 Integrations (Preview)")
        st.checkbox("GitHub", disabled=True, help="Coming soon")
        st.checkbox("Jira / Linear", disabled=True, help="Coming soon")
        st.checkbox("Google Calendar (Focus sync)", disabled=True, help="Coming soon")
        st.divider()
        if st.button("🗑️ Delete Project", type="secondary"):
            del st.session_state.projects[pid]
            del st.session_state.messages[pid]
            del st.session_state.knowledge_base[pid]
            st.session_state.current_project = None
            st.rerun()