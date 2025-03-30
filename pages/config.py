import streamlit as st
import json
import os

# Inicializar session_state para o login
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False


CONFIG_FILE = "config.json"
AUTH_PASSWORD = "Eduardo13"  # Defina a senha para acessar as configurações


# Criar arquivo JSON padrão se não existir
if not os.path.exists(CONFIG_FILE):
    config_data = {
        "CLIENT_ID": "",
        "CLIENT_SECRET": "",
        "REFRESH_TOKEN": "",
        "PASTA_ID_FISCAIS": "",
        "PLANILHAS_FISCAIS": {
            "Centro-Oeste": "",
            "Nordeste": "",
            "Sudeste": "",
            "Sul": "",
            "Norte": ""
        },
        "PASTA_ID_ORCAMENTO": "",
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

# Função para carregar configurações
def carregar_configuracoes():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# Função para salvar configurações
def salvar_configuracoes(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

st.title("🔒 Login para Configurações")
# Se o usuário não está autenticado, pede senha
if not st.session_state["autenticado"]:
    senha = st.text_input("Digite a senha para acessar:", type="password")
    if st.button("🔑 Entrar"):
        if senha == AUTH_PASSWORD:
            st.session_state["autenticado"] = True
            st.success("✅ Acesso concedido!")
            st.rerun()
        else:
            st.error("❌ Senha incorreta! Tente novamente.")

# Se já está autenticado, mostra configurações
if st.session_state["autenticado"]:
    # Carregar configurações
    config = carregar_configuracoes()

    # Exibir configurações atuais antes da edição
    st.subheader("📌 Configurações Atuais")
    st.json(config)  # Mostra o JSON formatado na tela

    st.markdown("---")

    # Exibir campos editáveis
    st.subheader("🛠️ Editar Credenciais OAuth 2.0")
    config["CLIENT_ID"] = st.text_input("CLIENT_ID", config["CLIENT_ID"])
    config["CLIENT_SECRET"] = st.text_input("CLIENT_SECRET", config["CLIENT_SECRET"])
    config["REFRESH_TOKEN"] = st.text_input("REFRESH_TOKEN", config["REFRESH_TOKEN"])
    config["PASTA_ID_FISCAIS"] = st.text_input("PASTA_ID_FISCAIS", config["PASTA_ID_FISCAIS"])
    config["PASTA_ID_ORCAMENTO"] = st.text_input("PASTA_ID_ORCAMENTO", config["PASTA_ID_ORCAMENTO"])

    st.subheader("📂 Editar ID das Planilhas por Região")
    for regiao in config["PLANILHAS_FISCAIS"]:
        config["PLANILHAS_FISCAIS"][regiao] = st.text_input(f"{regiao}", config["PLANILHAS_FISCAIS"][regiao])

    # Botão para salvar
    if st.button("💾 Salvar Configurações"):
        salvar_configuracoes(config)
        st.success("✅ Configurações salvas com sucesso!")

    # Botão de logout
    if st.button("🚪 Sair"):
        st.session_state["autenticado"] = False
        st.rerun()