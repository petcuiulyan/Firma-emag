"""Asistent AI (chat) cu acces optional la datele aplicatiei."""
import streamlit as st

import core_ai as ai
import core_assistant as asst
import view_common as c


def render():
    st.title("🤖 Asistent AI")
    key = c.api_key()
    with st.expander("⚙️ Conexiune AI", expanded=not key):
        try:
            from_secrets = bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
        except Exception:
            from_secrets = False
        if from_secrets:
            st.success("Cheia API este configurată în Streamlit Secrets.")
        else:
            k = st.text_input("Cheie API Anthropic", type="password", value=st.session_state.get("ai_key", ""),
                              help="Rămâne doar în sesiunea curentă. Permanent: Streamlit Cloud → Settings → Secrets → ANTHROPIC_API_KEY = \"sk-ant-...\"")
            if k != st.session_state.get("ai_key", ""):
                st.session_state["ai_key"] = k; st.rerun()
        m = st.text_input("Model", value=c.ai_model())
        st.session_state["ai_model"] = m
    send = st.toggle("Trimite asistentului datele din aplicație (comenzi, costuri, marje, luni)", value=True,
                     help="Fără date, asistentul răspunde doar general. Cu date, conținutul rezumat se trimite către API-ul Anthropic.")
    if not key:
        st.info("Introdu cheia API mai sus ca să pornești chatul."); return

    hist = st.session_state.setdefault("chat", [])
    if st.button("🗑️ Golește conversația", disabled=not hist):
        st.session_state["chat"] = []; st.rerun()
    for msg in hist:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    q = st.chat_input("Întreabă ceva: de ce e mică marja la un produs, cât a costat transportul, ce regim fiscal merge...")
    if q:
        hist.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        system = asst.SYSTEM
        if send:
            d, s, oc, lc = c.compute_all()
            system += "\nDATELE APLICAȚIEI:\n" + asst.build_context(d, s, oc, lc, d["months"])
        with st.chat_message("assistant"):
            with st.spinner("Se gândește..."):
                try:
                    ans = ai.chat(hist[-20:], system, key, c.ai_model())
                except Exception as e:
                    ans = f"⚠️ Eroare la apelul API: {e}"
            st.markdown(ans)
        hist.append({"role": "assistant", "content": ans})
