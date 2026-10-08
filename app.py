"""Import Calculator – punct de intrare Streamlit. Fiecare sectiune e in views/<nume>.py, iar calculele in core/<nume>.py."""
import streamlit as st

import view_dashboard as dashboard
import view_catalog_pi as catalog_pi
import view_new_order as new_order
import view_orders as orders
import view_cost as cost
import view_transport as transport
import view_margins as margins
import view_fiscal as fiscal
import view_settings as settings

st.set_page_config(page_title="Import Calculator", page_icon="📦", layout="wide")

pages = {
    "Prezentare": [st.Page(dashboard.render, title="Dashboard", icon="📊", url_path="dashboard", default=True)],
    "Operare": [
        st.Page(catalog_pi.render, title="Produse & PI", icon="📦", url_path="produse"),
        st.Page(new_order.render, title="Comandă nouă", icon="🛒", url_path="comanda-noua"),
        st.Page(orders.render, title="Comenzi", icon="🧾", url_path="comenzi"),
        st.Page(cost.render, title="Cost per bucată", icon="💶", url_path="cost"),
        st.Page(transport.render, title="Capacitate transport", icon="🚚", url_path="transport"),
    ],
    "Analiză": [
        st.Page(margins.render, title="Marjă per produs", icon="📈", url_path="marja"),
        st.Page(fiscal.render, title="Fiscal", icon="🏛️", url_path="fiscal"),
    ],
    "Sistem": [st.Page(settings.render, title="Setări & Backup", icon="⚙️", url_path="setari")],
}
st.navigation(pages).run()
