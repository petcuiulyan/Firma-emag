# Import Calculator

Aplicatie Streamlit: cost real per bucata (RON/EUR/USD), comenzi cu curs si transport propriu, import PI furnizori, capacitate transport, marja, fiscal.

Pornire: `pip install -r requirements.txt` apoi `streamlit run app.py`. Main file pe Streamlit Cloud: `app.py`.

Structura plata: `core_*.py` = calculele pe sectiuni, `view_*.py` = paginile, `app.py` = intrarea.
Datele se salveaza in folderul `data/` (creat automat). Pe Streamlit Cloud se pierd la repornire - foloseste Setari & Backup.
