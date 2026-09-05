import os
import signal
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

_UI_DIR = Path(__file__).resolve().parent
if str(_UI_DIR) not in sys.path:
    sys.path.insert(0, str(_UI_DIR))

from api_client import OrchestratorError, send_message

API_BASE_URL = os.getenv("BRO_API_URL", "http://localhost:8000")
API_PORT = urlparse(API_BASE_URL).port or 8000


def _kill_listeners_on_port(port: int) -> None:
    try:
        pids = subprocess.check_output(
            ["lsof", "-tiTCP:" + str(port), "-sTCP:LISTEN"], text=True
        ).split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pids = []
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ProcessLookupError, ValueError):
            pass


def _shutdown_everything(api_port: int) -> None:
    """Kill the API (by port) and this Streamlit process itself.

    Run on a short delay from a background thread so the UI has time to
    render/flush the "shutting down" message before the process exits.
    A fallback for when Ctrl+C in the launching terminal doesn't reach these
    processes (e.g. run via an IDE debug console rather than a real TTY).
    """
    _kill_listeners_on_port(api_port)
    os.kill(os.getpid(), signal.SIGTERM)

st.set_page_config(page_title="BRO", page_icon="🧭")
st.title("🧭 Business Resiliance Operator")
st.caption("Ask about HR, finance, documents, or anything else your business needs.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_invoked_specialists" not in st.session_state:
    st.session_state.last_invoked_specialists = []

with st.sidebar:
    st.subheader("Session")
    st.caption(f"API: {API_BASE_URL}")
    st.caption(f"Session ID: {st.session_state.session_id}")

    if st.button("New conversation"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.last_invoked_specialists = []
        st.rerun()

    if st.session_state.last_invoked_specialists:
        with st.expander("Last response: specialists invoked", expanded=False):
            for specialist in st.session_state.last_invoked_specialists:
                st.write(f"- {specialist}")

    with st.expander("Danger zone"):
        st.caption("Stops the API server and this UI. Use if Ctrl+C in the terminal isn't working.")
        if st.button("Stop servers", type="primary"):
            st.warning("Shutting down the API and this UI...")
            threading.Timer(1.0, _shutdown_everything, args=(API_PORT,)).start()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Type your message...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = send_message(
                    API_BASE_URL, st.session_state.session_id, user_input
                )
            except OrchestratorError as exc:
                st.error(
                    "Sorry, something went wrong reaching the orchestrator. "
                    "Please try again in a moment."
                )
                st.caption(str(exc))
            else:
                response_text = result.get("response", "")
                metadata = result.get("metadata", {})
                st.session_state.last_invoked_specialists = metadata.get(
                    "invoked_specialists", []
                )

                st.markdown(response_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response_text}
                )

                chart_data = metadata.get("chart_data")
                if chart_data:
                    st.line_chart(chart_data)

                document = metadata.get("document")
                if document:
                    st.download_button(
                        label=f"Download {document.get('filename', 'document')}",
                        data=document.get("content", b""),
                        file_name=document.get("filename", "document"),
                    )
