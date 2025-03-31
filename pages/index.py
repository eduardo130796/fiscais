import streamlit as st


st.title("🎯 Bem-vindo ao Meu Projeto!")
st.write("Explore as funcionalidades desenvolvidas para facilitar a gestão e atualização das planilhas.")

# Criando cards interativos
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🕵️‍♂️ Planilha dos Fiscais")
    st.write("Atualize automaticamente a planilha com dados dos fiscais de forma simples e rápida.")
    st.page_link("pages/fiscais.py", label="Fiscais", icon="🕵️‍♂️")

with col2:
    st.markdown("### 📈 Planilha de Orçamento")
    st.write("Faça a atualização do orçamento de maneira ágil, mantendo todos os dados organizados.")
    st.page_link("pages/orcam.py", label="Orçamento", icon="📈")
    
with col3:
    st.markdown("### 📊 Painel Orçamentário")
    st.write("Painel Gerencial Orçamentário.")
    st.page_link("pages/relatorio.py", label="Relatório", icon="📊")

    # Criando cards interativos
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### ⚙️ Configurações")
    st.write("Edite as credenciais OAuth e outras configurações.")
    st.page_link("pages/config.py", label="Configurações", icon="⚙️")



# Rodapé fixo com largura total
rodape = """
    <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f8f9fa;
            text-align: center;
            padding: 10px;
            font-size: 14px;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
            z-index: 100;
        }
    </style>
    <div class="footer">
        Desenvolvido por <strong>Eduardo Júnior</strong> | 2025
    </div>
"""

# Exibir o rodapé na interface
st.markdown(rodape, unsafe_allow_html=True)