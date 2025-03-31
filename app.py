import streamlit as st

st.set_page_config(page_title="Meu Projeto", page_icon="🗂️", layout="wide")
# --- Sidebar ---


    

pages = {
    "Pagina Inícial":[
        st.Page("pages/index.py", title="Início", icon="🏠"),
    ],
    "Funcionalidades": [
        st.Page("pages/fiscais.py", title="Planilha de Fiscais", icon="🕵️‍♂️"),
        st.Page("pages/orcam.py", title="Planilha de Orçamento", icon="📈"),
    ],
    "Relatórios": [
        st.Page("pages/relatorio.py", title="Painel Orçamentário", icon="📊"),
    ],

    "Configurações": [
        st.Page("pages/config.py", title="Configurações", icon="⚙️"),
    ],
}
pg = st.navigation(pages)
pg.run()

with st.sidebar:
    # Configuração da página
    st.caption("© 2025 - Eduardo Júnior")