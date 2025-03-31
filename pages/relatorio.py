import requests
import pandas as pd
import streamlit as st
import time
from io import StringIO  
import io
import plotly.express as px
from datetime import datetime
from pages.config import carregar_configuracoes

#st.set_page_config(layout="wide")

config = carregar_configuracoes()
# Suas credenciais OAuth 2.0
CLIENT_ID = config["CLIENT_ID"]
CLIENT_SECRET = config["CLIENT_SECRET"]
REFRESH_TOKEN = config["REFRESH_TOKEN"]  # Use o refresh_token que você obteve na primeira autenticação

# ID da pasta específica
PASTA_ID = config["PASTA_ID_ORCAMENTO"]  # Coloque o ID da sua pasta aqui

# Função para renovar o token usando o refresh_token
def renovar_token(refresh_token):
    url = "https://oauth2.googleapis.com/token"
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        token_info = response.json()
        access_token = token_info.get('access_token')
        return access_token
    else:
        return None
# Função para obter o token de acesso
def get_access_token():
    global ACCESS_TOKEN
    if not hasattr(get_access_token, "expires_at") or time.time() > get_access_token.expires_at:
        # Se o token tiver expirado ou não estiver definido, renove-o
        ACCESS_TOKEN = renovar_token(REFRESH_TOKEN)
        get_access_token.expires_at = time.time() + 3600  # Defina o tempo de expiração como 1 hora (3600 segundos)
    return ACCESS_TOKEN

def verificar_token():
    """Simula a verificação do token"""
    try:
        # Aqui você faz a verificação real, como chamar uma API, verificar data de expiração, etc.
        token_valido = get_access_token()  # Substitua por sua lógica real

        if not token_valido:
            st.error("❌ **Seu token expirou!** Entre em contato com o suporte para atualizar suas credenciais.")
            st.stop()  # Para a execução do Streamlit imediatamente
    except Exception as e:
        st.error(f"⚠️ Erro ao verificar o token: {e}")
        st.stop()

# Antes de qualquer outra execução, verificar o token
verificar_token()

def listar_arquivos(pasta_id):
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{pasta_id}' in parents and trashed=false",  # Busca apenas arquivos na pasta especificada
        "fields": "files(id, name, mimeType)"  # Adiciona 'mimeType' para identificar o tipo de arquivo
    }
    headers = {"Authorization": f"Bearer {get_access_token()}"}

    response = requests.get(url, params=params, headers=headers)
    arquivos = response.json().get("files", [])
    
    if arquivos:
        print(f"📂 Arquivos na pasta {pasta_id}:")
        for arquivo in arquivos:
            print(f"📄 {arquivo['name']} (ID: {arquivo['id']}) - Tipo: {arquivo['mimeType']}")
        return arquivos
    else:
        print("❌ Nenhum arquivo encontrado na pasta.")
        return []

def excluir_arquivo(file_id):
    """Excluir o arquivo após o uso."""
    access_token = get_access_token()
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    if response.status_code == 204:
        print(f"Arquivo {file_id} excluído com sucesso.")
    else:
        st.error(f"Erro ao excluir o arquivo {file_id}: {response.text}")

def converter_para_google_sheets(file_id, file_name):
    """Converte um arquivo .xlsx para Google Sheets e exclui o arquivo convertido após o uso."""
    access_token = get_access_token()
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}/copy"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "name": f"{file_name} (Convertido)",
        "mimeType": "application/vnd.google-apps.spreadsheet"
    }
    
    response = requests.post(url, headers=headers, json=params)
    
    if response.status_code == 200:
        new_file_id = response.json().get("id")
        return new_file_id  # Retorna o novo ID do arquivo convertido
    else:
        st.error(f"Erro ao converter {file_name}: {response.text}")
        return None

# Função para limpar e converter valores monetários
def converter_monetario(valor):
    if isinstance(valor, str):  # Verificar se é uma string
        valor = valor.strip()  # Remover espaços extras no início e no fim
        valor = valor.replace("R$", "")  # Remover o símbolo R$
        valor = valor.replace(" ", "")  # Remover espaços extras no meio
        valor = valor.replace(".", "")  # Remover pontos, caso haja como separador de milhar
        valor = valor.replace(",", ".")  # Substituir a vírgula por ponto para conversão de float
        try:
            return float(valor)  # Converter para float
        except ValueError:
            return 0.0  # Caso não consiga converter, retorna 0.0
    return valor  # Se não for string, retorna o valor original

def baixar_arquivos_csv(pasta_id):
    access_token = get_access_token()
    arquivos = listar_arquivos(pasta_id)

    df_combinado = pd.DataFrame()

    # Lista para armazenar os IDs dos arquivos processados
    arquivos_processados = []

    for arquivo in arquivos:
        file_id = arquivo["id"]
        file_name = arquivo["name"]
        mime_type = arquivo["mimeType"]

        # Se for um arquivo .xlsx, precisamos convertê-lo primeiro
        if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            novo_id = converter_para_google_sheets(file_id, file_name)
            if novo_id:
                file_id = novo_id  # Usa o novo ID do arquivo convertido
                mime_type = "application/vnd.google-apps.spreadsheet"
            else:
                continue  # Se a conversão falhar, pula esse arquivo

        # Agora podemos exportar como CSV
        if mime_type == "application/vnd.google-apps.spreadsheet":
            export_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=text/csv"
        else:
            continue  # Ignora outros tipos de arquivo

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(export_url, headers=headers)
            response.raise_for_status()  # Levanta uma exceção para status de erro
        except requests.exceptions.RequestException as e:
            st.error(f"Erro ao baixar {file_name}: {e}")
            continue

        if response.status_code == 200:
            # Lê o CSV com pandas
            df = pd.read_csv(io.StringIO(response.text), encoding='ISO-8859-1', sep=',', skiprows=4)  # Ignora as 4 primeiras linhas, se necessário
            
            # Corrigir qualquer string mal codificada
            df = df.applymap(lambda x: x.encode('latin1').decode('utf-8') if isinstance(x, str) else x)
            # Mantém apenas as colunas até a coluna AC (coluna 29)
            colunas_necessarias = df.columns[:30]  # Colunas até a 30ª (índice 29)
            df = df[colunas_necessarias]
            
            coluna_contrato = df.columns[2]  # Coluna de contrato

            df = df[df[coluna_contrato].notna()]
            # Renomeando colunas para facilitar
            df.columns = ["Regiao", "Processo", "Contrato", "Objeto", "Nota Empenho", "Valor Empenhado", "Valor Pago", "Valor Global", "Valor Anual", "Valor Mensal", "Status", "Ultima Repactuacao", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total Anual", "Indice", "Evolucao", "Reajuste", "Reforço/Remanejamento", " "]
            
            # Convertendo valores financeiros
            colunas_valores = ["Valor Empenhado", "Valor Pago", "Valor Global", "Valor Anual", "Valor Mensal", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total Anual", "Reforço/Remanejamento"]
            for col in colunas_valores:
                # Aplicar a função nas colunas de interesse
                df[col] = df[col].apply(converter_monetario)

            df["Fonte"] = file_name  # Adiciona uma coluna com o nome do arquivo
            df_combinado = pd.concat([df_combinado, df], ignore_index=True)
            arquivos_processados.append(file_id)  # Armazena o ID do arquivo processado
        else:
            st.error(f"Erro ao baixar {file_name}: {response.text}")

    # Após processar todos os arquivos, excluir os arquivos processados
    for file_id in arquivos_processados:
        excluir_arquivo(file_id)

    return df_combinado
    

# Verificar se os dados já estão salvos no session_state
if "dados" not in st.session_state:
    st.session_state.dados = None  # Inicializar com None
if "ultima_atualizacao" not in st.session_state:
    st.session_state.ultima_atualizacao = None  # Inicializar com None

# Função para processar e salvar os dados no session_state
def processar_dados():
    st.session_state.dados = baixar_arquivos_csv(PASTA_ID)  # Chama a função para baixar e processar os dados
    st.session_state.ultima_atualizacao = time.strftime('%Y-%m-%d %H:%M:%S')  # Armazenar a hora da última atualização
    st.success("📝 Dados carregados e salvos na memória.")

# Função para formatar os valores como R$ (Reais)
def formatar_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data):
    if data:
        # Verificar se a data está em formato string e converter para datetime
        if isinstance(data, str):
            data = datetime.strptime(data, "%Y-%m-%d %H:%M:%S")  # Ajuste conforme o formato da sua string
        return data.strftime("%d/%m/%Y %H:%M")
    return ""


def calcular_execucao(df):
    # Calcular execução em relação ao valor anual
    df['Execucao Percentual (Anual)'] = (df['Valor Pago'] / df['Valor Anual']) * 100
    
    # Calcular execução em relação ao valor empenhado
    df['Execucao Percentual (Empenhado)'] = (df['Valor Pago'] / df['Valor Empenhado']) * 100
    
    # Calcular percentual faltante de empenho para alcançar o valor anual
    df['Percentual Faltante de Empenho'] = ((df['Valor Anual'] - df['Valor Empenhado']) / df['Valor Anual']) * 100
    
    # Garantir que o percentual faltante não seja negativo
    df['Percentual Faltante de Empenho'] = df['Percentual Faltante de Empenho'].apply(lambda x: max(x, 0))
    
    return df
# Adicionar CSS para personalizar o layout e o botão
st.markdown(
    """
    <style>
    /* Estilizando o cabeçalho */
    .title {
        font-size: 50px;
        font-weight: bold;
        color: #4A90E2;
        text-align: center;
        padding: 0px;
    }

    /* Estilizando o botão */
    .stButton button {
        background-color: #4CAF50;  /* Verde */
        color: white;
        font-size: 16px;
        border-radius: 5px;
        padding: 12px 24px;
        border: none;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }
    .stButton button:hover {
        background-color: #45a049;  /* Cor mais escura ao passar o mouse */
    }

    /* Estilizando a info da última atualização */
    .stInfo {
        font-size: 14px;
        color: #555;
        text-align: center;
        padding: 0px 0;
        margin-bottom:50px
    }
    </style>
    """, unsafe_allow_html=True
)

# Cabeçalho com título e ícone
st.markdown('<div class="title">📊 Painel de Gestão Orçamentária</div>', unsafe_allow_html=True)

# Botão para atualizar os dados (colocado na sidebar)
with st.sidebar:
    if st.button("Atualizar Dados"):
        with st.spinner("Atualizando dados..."):
            st.session_state.dados = processar_dados()  # Atualiza os dados quando o botão for pressionado

# Verificar se os dados estão carregados no session_state
if st.session_state.dados is not None:
    df_local = st.session_state.dados
    
    # Exibir a hora da última atualização com formatação brasileira
    if st.session_state.ultima_atualizacao:
        ultima_atualizacao_formatada = formatar_data_br(st.session_state.ultima_atualizacao)
        st.markdown(f'<div class="stInfo">Última atualização: {ultima_atualizacao_formatada}</div>', unsafe_allow_html=True)
    
    df_local["Regiao"] = df_local["Regiao"].str.strip().str.upper()
    # Sidebar para filtros
    st.sidebar.header("Filtros")
    regioes = st.sidebar.multiselect("Selecione a Região", df_local["Regiao"].unique())
    objeto = st.sidebar.multiselect("Selecione o Objeto", df_local["Fonte"].unique())
    

    # Aplicar filtros
    if regioes:
        df_local = df_local[df_local["Regiao"].isin(regioes)]
    if objeto:
        df_local = df_local[df_local["Fonte"].isin(objeto)]
    # Selecione o Contrato com uma opção inicial "Selecione um contrato"
    contrato = st.sidebar.selectbox("Selecione um Contrato", options=["Selecione um contrato"] + list(df_local["Contrato"].unique()))

    # Filtrar os dados apenas se um contrato for selecionado
    if contrato != "Selecione um contrato":
        df_local = df_local[df_local["Contrato"] == contrato]

   


    if contrato != "Selecione um contrato":
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Valor Anual", formatar_real(df_local['Valor Anual'].sum()))
            col2.metric("💰 Valor Empenhado", formatar_real(df_local['Valor Empenhado'].sum()))
            col3.metric("💵 Valor Pago", formatar_real(df_local['Valor Pago'].sum()))
            with col4:
                # Cálculo da diferença entre o valor anual e o valor empenhado
                df_local['Diferença'] = df_local['Valor Empenhado'] - df_local['Valor Anual']

                # Calcular o total de valores a serem anulados ou reforçados
                valor_anular = df_local[df_local['Diferença'] > 0]['Diferença'].sum()
                valor_reforcar = df_local[df_local['Diferença'] < 0]['Diferença'].sum()

                # Mostrar os valores de reforço ou anulação, com as cores adequadas
                if valor_reforcar < 0:
                    st.metric("⚠️ Ação Necessária - Reforçar",
                            formatar_real(abs(valor_reforcar)), "Reforçar",
                            delta_color="inverse")  # 'inverse' para destacar como algo negativo (precisa reforçar)
                else:
                    st.metric("✅ Ação Necessária - Anular",
                            formatar_real(abs(valor_anular)), "Anular",
                            delta_color="normal")  # 'normal' para algo positivo (pode anular)
                    

            df_contrato = df_local[df_local['Contrato'] == contrato]
    
            # Calcular a execução e os percentuais para o contrato selecionado
            df_contrato = calcular_execucao(df_contrato)
            


            col1, col2 = st.columns([1,1])
            with col1:        
                # Exibir gráficos e dados para o contrato selecionado
                st.subheader(f"📊 Detalhes do Contrato: {contrato}")
                
                # Aqui você pode adicionar dados complementares do contrato (ex: valores totais)
                contrato_info = df_local[df_local["Contrato"] == contrato].iloc[0]
                contrato_info_perc = df_contrato[df_contrato["Contrato"] == contrato].iloc[0]
                st.write(f"Região: {contrato_info['Regiao']}")
                st.write(f"Objeto: {contrato_info['Objeto']}")
                st.write(f"Valor Mensal: {formatar_real(contrato_info['Valor Mensal'])}")
                st.write(f"Status Repactuação/Reajuste: {(contrato_info['Status'])}")
                st.write(f"🔹 **Execução do Valor Anual (Pago / Anual):** {contrato_info_perc['Execucao Percentual (Anual)']:.2f}%")
                st.write(f"🔹 **Execução do Valor Empenhado (Pago / Empenhado):** {contrato_info_perc['Execucao Percentual (Empenhado)']:.2f}%")
                st.write(f"🔹 **Percentual Faltante de Empenho (Falta para Anual):** {contrato_info_perc['Percentual Faltante de Empenho']:.2f}%")
            
            with col2: 
            # Gráfico de barras para mostrar o valor anual, empenhado e pago
                st.subheader("📊 Comparação de Valores: Anual, Empenhado e Pago")
                fig_valores = px.bar(
                    x=["Valor Anual", "Valor Empenhado", "Valor Pago"], 
                    y=[contrato_info["Valor Anual"], contrato_info["Valor Empenhado"], contrato_info["Valor Pago"]],
                    labels={"x": "Tipo de Valor", "y": "Valor (R$)"},
                    title="Comparação de Valores: Anual, Empenhado e Pago",
                    color=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                    color_discrete_map={
                        "Valor Anual": "#2ca02c", 
                        "Valor Empenhado": "#1f77b4", 
                        "Valor Pago": "#ff7f0e"
                    }
                )

                # Ajustes de layout para o gráfico
                # Criar texto formatado para cada barra
                for i, trace in enumerate(fig_valores.data):
                    trace.text = [formatar_real(val) for val in trace.y]
                fig_valores.update_layout(
                    height=400,
                    xaxis_title="Tipo de Valor",
                    yaxis_title="Valor (R$)",
                    showlegend=False,
                    bargap=0.2  # Espaçamento entre as barras
                )

                # Exibir o gráfico de comparação de valores
                st.plotly_chart(fig_valores)



                # Converter as colunas de meses em uma única coluna de "Mês"
            meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            
            # Transformar as colunas de meses em um formato longo
            df_melt = df_local.melt(id_vars=["Contrato", "Regiao"], value_vars=meses, var_name="Mês", value_name="Valor Pago Mensal")
            
            # Agrupar os dados por contrato e mês para calcular os valores pagos
            df_pagamento = df_melt.groupby(["Contrato", "Mês"], as_index=False)["Valor Pago Mensal"].sum()

            # Ordenar os meses com base na lista meses_ordem
            df_pagamento["Mês"] = pd.Categorical(df_pagamento["Mês"], categories=meses, ordered=True)
            df_pagamento = df_pagamento.sort_values("Mês")

            # Gráfico de barras de pagamento mês a mês
            st.subheader("📊 Pagamento Mês a Mês por Contrato")
            fig_pagamento = px.bar(
                df_pagamento,
                x="Mês",
                y="Valor Pago Mensal",
                color="Contrato",
                title="Pagamentos Mês a Mês por Contrato",
                labels={"Mês": "Mês", "Valor Pago Mensal": "Valor Pago (R$)"},
                barmode="group"
            )

            for i, trace in enumerate(fig_pagamento.data):
                    trace.text = [formatar_real(val) for val in trace.y]
            fig_pagamento.update_layout(
                
                height=500,
                xaxis_title="Mês",
                yaxis_title="Valor Pago (R$)",
                showlegend=True
            )

            # Exibir o gráfico de pagamento
            st.plotly_chart(fig_pagamento)
    else:
        col1, col2, col3, col4, col5 = st.columns([1,2,2,2,2])
        col1.metric("Total de Contratos:", len(df_local))
        col2.metric("💰 Valor Anual Total", formatar_real(df_local['Valor Anual'].sum()))
        col3.metric("💰 Valor Empenhado Total", formatar_real(df_local['Valor Empenhado'].sum()))
        col4.metric("💵 Valor Pago Total", formatar_real(df_local['Valor Pago'].sum()))
        with col5:
            # Cálculo da diferença entre o valor anual e o valor empenhado
            df_local['Diferença'] = df_local['Valor Empenhado'] - df_local['Valor Anual']

            # Calcular o total de valores a serem anulados ou reforçados
            valor_anular = df_local[df_local['Diferença'] > 0]['Diferença'].sum()
            valor_reforcar = df_local[df_local['Diferença'] < 0]['Diferença'].sum()

            # Mostrar os valores de reforço ou anulação, com as cores adequadas
            if valor_reforcar < 0:
                st.metric("⚠️ Ação Necessária - Reforçar",
                        formatar_real(abs(valor_reforcar)),"Reforçar",
                        delta_color="inverse")  # 'inverse' para destacar como algo negativo (precisa reforçar)
            else:
                st.metric("✅ Ação Necessária - Anular",
                        formatar_real(abs(valor_anular)),"Anular",
                        delta_color="normal")  # 'normal' para algo positivo (pode anular)

        # Ordenar as regiões pelo maior valor empenhado
        # Agrupar e somar os valores de "Valor Empenhado", "Valor Pago" e "Valor Anual" por região
        col1, col2 = st.columns([1,1])
        with col1:
            st.subheader("📊 Comparação por Região")
            # Agrupar os dados
            df_grafico = df_local.groupby("Regiao", as_index=False)[["Valor Anual", "Valor Empenhado", "Valor Pago"]].sum()

            # Ordenar as regiões pelo maior valor empenhado
            df_grafico = df_grafico.sort_values(by="Valor Empenhado", ascending=False)

            

            # Criar o gráfico de barras para mostrar as somas totais
            fig = px.bar(
                df_grafico,
                x="Regiao",
                y=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                barmode="group",
                title="💰 Comparação de Valores Empenhados, Pagos e Anuais por Região",  # Habilita a exibição automática dos valores
                color_discrete_map={
                    "Valor Empenhado": "#1f77b4",
                    "Valor Pago": "#ff7f0e",
                    "Valor Anual": "#2ca02c",  # Cor verde para o valor anual
                }
            )

            # Criar texto formatado para cada barra
            for i, trace in enumerate(fig.data):
                trace.text = [formatar_real(val) for val in trace.y]

            # Ajustes para facilitar a leitura
            fig.update_layout(
                xaxis_title="Região",
                yaxis_title="Valor (R$)",
                legend_title="Tipo de Valor",
                uniformtext_minsize=10,
                uniformtext_mode="hide",
                bargap=0.15,  # Espaçamento entre os grupos de barras
                height=500,  # Definir altura do gráfico para melhor visualização # Centrar o título do gráfico
            )

            # Exibir o gráfico
            st.plotly_chart(fig)


        with col2:
            # --- Bloco 2: Comparação por Objeto ---
            st.subheader("📊 Comparação por Objeto")

            # Agrupar os dados por Objeto (Fonte)
            df_grafico_objeto = df_local.groupby("Fonte", as_index=False)[["Valor Anual", "Valor Empenhado", "Valor Pago"]].sum()

            # Ordenar os objetos pelo maior valor empenhado
            df_grafico_objeto = df_grafico_objeto.sort_values(by="Valor Empenhado", ascending=False)

            

            # Criar o gráfico por Objeto
            fig_objeto = px.bar(
                df_grafico_objeto,
                x="Fonte",
                y=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                barmode="group",
                title="💰 Comparação de Valores Empenhados, Pagos e Anuais por Objeto",
                
                color_discrete_map={
                    "Valor Empenhado": "#1f77b4",
                    "Valor Pago": "#ff7f0e",
                    "Valor Anual": "#2ca02c",
                }
            )

            # Definir um limite baseado na média dos valores para ajustar a posição
            limite = df_grafico_objeto[["Valor Anual", "Valor Empenhado", "Valor Pago"]].mean().mean()

            # Ajustar a posição do texto: fora para valores pequenos, dentro para valores grandes
            for trace in fig_objeto.data:
                valores = trace.y  # Lista de valores
                trace.text = [formatar_real(val) for val in valores]  # Formata os valores
                trace.textposition = ["outside" if val < limite else "inside" for val in valores]
    

            # Ajustes para facilitar a leitura
            fig_objeto.update_layout(
                xaxis_title="Objeto",
                yaxis_title="Valor (R$)",
                legend_title="Tipo de Valor",
                uniformtext_minsize=10,
                uniformtext_mode="hide",
                bargap=0.15,  # Espaçamento entre os grupos de barras
                height=500,  # Definir altura do gráfico para melhor visualização # Centrar o título do gráfico
            )

            # Exibir o gráfico de Objeto
            st.plotly_chart(fig_objeto, use_container_width=True)
            
        st.write("__")

        # 1. Top 5 contratos com maior valor empenhado
        top_5_valor_empenhado = df_local[['Contrato', 'Objeto', 'Valor Empenhado', "Valor Anual"]].sort_values(by='Valor Empenhado', ascending=False).head(5)
        top_5_valor_empenhado['Valor Empenhado'] = top_5_valor_empenhado['Valor Empenhado'].apply(formatar_real)
        top_5_valor_empenhado['Valor Anual'] = top_5_valor_empenhado['Valor Anual'].apply(formatar_real)
        st.subheader("🔝 Top 5 Contratos com Maior Valor Empenhado")
        st.write(top_5_valor_empenhado)

        # 2. Top 5 contratos com maior valor anual
        top_5_valor_anual = df_local[['Contrato', 'Objeto', 'Valor Empenhado', 'Valor Anual']].sort_values(by='Valor Anual', ascending=False).head(5)
        top_5_valor_anual['Valor Anual'] = top_5_valor_anual['Valor Anual'].apply(formatar_real)
        top_5_valor_anual['Valor Empenhado'] = top_5_valor_anual['Valor Empenhado'].apply(formatar_real)
        st.subheader("🔝 Top 5 Contratos com Maior Valor Anual")
        st.write(top_5_valor_anual)

        # 3. Contratos com maior diferença entre o valor anual e o valor empenhado
        df_local['Diferenca'] = df_local['Valor Anual'] - df_local['Valor Empenhado']
        top_5_diferenca = df_local[['Contrato', 'Objeto', 'Valor Empenhado', 'Valor Anual', 'Diferenca']].sort_values(by='Diferenca', ascending=False).head(5)
        top_5_diferenca['Diferenca'] = top_5_diferenca['Diferenca'].apply(formatar_real)
        top_5_diferenca['Valor Anual'] = top_5_diferenca['Valor Anual'].apply(formatar_real)
        top_5_diferenca['Valor Empenhado'] = top_5_diferenca['Valor Empenhado'].apply(formatar_real)
        st.subheader("🔝 Top 5 Contratos com Maior Diferença (Valor Anual - Valor Empenhado)")
        st.write(top_5_diferenca)
   


else:
    st.warning("🚨 Nenhum dado carregado. Clique em 'Atualizar Dados' para baixar os dados.")
