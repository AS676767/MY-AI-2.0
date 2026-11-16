
import streamlit as st
import os
from groq import Groq
from tavily import TavilyClient
from approved_sources import APPROVED_SOURCES
from urllib.parse import urlparse

# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="My Generative AI",
    page_icon="✨",
    layout="wide"
)

# ---------------- CUSTOM DESIGN ----------------

: #778196;
        font-si
st.markdown("""
<style>
    .stApp {
        background-color: #ffffff;
        color: #202938;
    }

    [data-testid="stSidebar"] {
        background-color: #f8f9fb;
        border-right: 1px solid #eeeeee;
    }

    [data-testid="stChatMessage"] {
        background-color: transparent;
        border: none;
        padding: 12px 18px;
    }

    .stChatInput textarea {
        border-radius: 14px;
    }

    h1, h2, h3 {
        color: #202938;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- GROQ CONNECTION ----------------

api_key = os.environ.get("GROQ_API_KEY")

try:
    api_key = st.secrets.get("GROQ_API_KEY", api_key)
except Exception:
    pass

if not api_key:
    st.error("Please configure your Groq API key.")
    st.stop()

client = Groq(api_key=api_key)
tavily_api_key = st.secrets.get("TAVILY_API_KEY", os.environ.get("TAVILY_API_KEY"))

if not tavily_api_key:
    st.error("Please configure your Tavily API key.")
    st.stop()

tavily = TavilyClient(api_key=tavily_api_key)
def search_approved_websites(question):
    approved_domains = list({
        urlparse(source).netloc.replace("www.", "")
        for source in APPROVED_SOURCES
    })

    results = tavily.search(
        query=question,
        search_depth="basic",
        max_results=5,
        include_domains=approved_domains
    )

    approved_results = []

    for result in results.get("results", []):
        url = result.get("url", "")
        domain = urlparse(url).netloc.replace("www.", "")

        if any(
            domain == approved or domain.endswith("." + approved)
            for approved in approved_domains
        ):
            approved_results.append({
                "url": url,
                "content": result.get("content", "")
            })

    return approved_results

# ---------------- CHAT HISTORY ----------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversations" not in st.session_state:
    st.session_state.conversations = []

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("## ✨ My Generative AI")
    st.caption("Your personal AI assistant")

    st.divider()

    if st.button("＋  New Chat", use_container_width=True):
        if st.session_state.messages:
            st.session_state.conversations.append(
                st.session_state.messages.copy()
            )
        st.session_state.messages = []
        st.rerun()

    st.markdown("### Recent conversations")

    for i, conversation in enumerate(
        reversed(st.session_state.conversations)
    ):
        if conversation:
            title = conversation[0]["content"][:25]

            st.caption(f"💬 {title}")

    st.divider()

    if st.button("Clear Current Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

  
    st.caption("Powered by Groq AI")

# ---------------- MAIN SCREEN ----------------

if not st.session_state.messages:

    st.markdown(
        '<div class="main-title">What can I help you with?</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Ask questions, explore ideas, '
        'or get help with anything.</div>',
        unsafe_allow_html=True
    )

# Display previous messages

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------- USER INPUT ----------------

prompt = st.chat_input("Message My Generative AI...")

if prompt:

    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):


            try:
                retrieved_matches = search_approved_websites(prompt)

                if retrieved_matches:
                    source_context = "\n\n".join(
                        [
                            f"Source URL: {item['url']}\nInformation: {item['content']}"
                            for item in retrieved_matches
                        ]
                    )
                else:
                    source_context = "No information was found in the approved website database."

                system_message = {
                    "role": "system",
                    "content": (
                        "You are a student-friendly educational assistant. "
                        "Use only the approved-source information provided below. "
                        "Do not invent facts or pretend you found information that is not there. "
                        "If the sources do not answer the question, clearly say that "
                        "you could not find enough information in the approved sources. "
                        "Use simple, age-appropriate language. "
                        "Include the source URLs when using information.\n\n"
                        f"APPROVED SOURCE INFORMATION:\n{source_context}"
                    )
                }

                api_messages = [system_message] + st.session_state.messages

                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=api_messages,
                    max_tokens=1000
                )

                answer = response.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )

            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.session_state.messages.pop()

