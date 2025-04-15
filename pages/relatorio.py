import requests
import pandas as pd
import streamlit as st
import time
from io import StringIO  
import io
import os
import json
import plotly.express as px
from datetime import datetime, date
import calendar
import plotly.graph_objects as go
from pages.config import carregar_configuracoes
import math
import matplotlib.pyplot as plt


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


def preencher_valor_anual_proporcional(df, ano_referencia):
    def limpar_valor(v):
        if isinstance(v, str):
            v = v.replace("R$", "").replace(".", "").replace(",", ".").strip()
            try:
                return float(v)
            except:
                return 0.0
        return v

    def calcular_proporcional(data_inicio, data_fim, valor_mensal):
        dias_total = 0
        current = pd.Timestamp(data_inicio.year, data_inicio.month, 1)

        while current.date() <= data_fim:
            _, dias_mes = calendar.monthrange(current.year, current.month)
            inicio_mes = current
            fim_mes = current.replace(day=dias_mes)

            # Ajusta os limites
            if pd.Timestamp(data_inicio) > inicio_mes:
                inicio_mes = pd.Timestamp(data_inicio)
            if pd.Timestamp(data_fim) < fim_mes:
                fim_mes = pd.Timestamp(data_fim)

            dias_no_mes = (fim_mes - inicio_mes).days + 1

            # Verifica se o mês deve ser contado como cheio
            if inicio_mes.day == 1 and fim_mes.day == dias_mes:
                valor_mes = valor_mensal
            else:
                valor_mes = (valor_mensal / dias_mes) * dias_no_mes

            dias_total += valor_mes
            current += pd.DateOffset(months=1)
            current = current.replace(day=1)

        return dias_total

    df['Valor Mensal'] = df['Valor Mensal'].apply(limpar_valor)
    df['Ocorrência'] = df['Ocorrência'].astype(str).str.strip().str.lower()
    df['Data de Ocorrência'] = pd.to_datetime(df['Data de Ocorrência'], dayfirst=True, errors='coerce')
    df['Valor Anual Proporcional'] = None  # zera antes de preencher

    for i, row in df.iterrows():
        ocorrencia = row['Ocorrência']
        data_ocorrencia = row['Data de Ocorrência']
        valor_mensal = row['Valor Mensal']

        if pd.isnull(valor_mensal) or valor_mensal == 0:
            continue

        if ocorrencia == 'inicio' and not pd.isnull(data_ocorrencia):
            inicio_data = data_ocorrencia.date()
            fim_data = date(ano_referencia, 12, 31)

            if inicio_data <= fim_data:
                valor_total = calcular_proporcional(inicio_data, fim_data, valor_mensal)
                df.at[i, 'Valor Anual Proporcional'] = round(valor_total, 2)
            continue

        elif ocorrencia == 'rescisão' and not pd.isnull(data_ocorrencia):
            fim_data = data_ocorrencia.date()
            inicio_data = date(ano_referencia, 1, 1)

            if inicio_data <= fim_data:
                valor_total = calcular_proporcional(inicio_data, fim_data, valor_mensal)
                df.at[i, 'Valor Anual Proporcional'] = round(valor_total, 2)
            continue

        elif ocorrencia in ('nan', '', 'outro', 'não informado', 'ajuste', 'reajuste') or pd.isnull(ocorrencia):
            df.at[i, 'Valor Anual Proporcional'] = round(valor_mensal * 12, 2)
            continue

    return df



def baixar_arquivos_google_drive(arquivos):
    access_token = get_access_token()
    arquivos_download = []
    
    
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
            print(f"Erro ao baixar {file_name}: {e}")
            continue

        if response.status_code == 200:
            arquivos_download.append({
                "id": file_id,
                "name": file_name,
                "conteudo": io.StringIO(response.text)
            })
        else:
            print(f"Erro ao baixar {file_name}: {response.text}")

    return arquivos_download

def processar_dados_principais_csv():
    arquivos = [
    {"id": "1E2xiSA0VwiiqS04iHhvmiIP-5RyGJvDf", "name": "Vigilância.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    {"id": "1bpsBDegUletMd07SjE0EpbX1zgjl_6zj", "name": "Locação de Imóvel.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    {"id": "1iGlxRvoF5gjn6r0CUsyRVakmph6cXpD3", "name": "Limpeza e Conservação.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    {"id": "1RPQADGPfy4b6hGtNMg-p6o93y3H6bJVO", "name": "Diversos.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    {"id": "1-yM9S_yPYWmt3ozLkow6QIaJD31O8Huo", "name": "Ar condicionado.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    # Outros arquivos
    ]

    arquivos_download = baixar_arquivos_google_drive(arquivos)

    df_combinado = pd.DataFrame()
    df_combinado_1 = pd.DataFrame()

    # Processar cada arquivo baixado
    for arquivo in arquivos_download:
        file_id = arquivo["id"]
        file_name = arquivo["name"]
        arquivo_csv = arquivo["conteudo"]
        df = pd.read_csv(arquivo_csv, encoding='ISO-8859-1', sep=',', skiprows=4, dayfirst=True)  # Ignora as 4 primeiras linhas, se necessário
        
        # Corrigir e limpar os dados
        df.columns = df.columns.str.strip().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        df = df.applymap(lambda x: x.encode('latin1').decode('utf-8') if isinstance(x, str) else x)
        
        # Limitar as colunas
        colunas_necessarias = df.columns[:31]  # Colunas até a 30ª (índice 29)
        df = df[colunas_necessarias]
        df_comple = df.copy()
        coluna_contrato = df.columns[2]  # Coluna de contrato
        df = df[df[coluna_contrato].notna()]
        # Renomeando colunas
        df.columns = ["Regiao", "Processo", "Contrato", "Objeto", "Nota Empenho", "Valor Empenhado", "Valor Pago", "Valor Global", 
                      "Valor Anual", "Valor Mensal", "Status", "Ultima Repactuacao", "Ocorrência", "Data de Ocorrência", 
                      "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total Anual", 
                      "Indice", "Evolucao", "Reajuste", "Reforço/Remanejamento"]

        # Convertendo valores financeiros
        colunas_valores = ["Valor Empenhado", "Valor Pago", "Valor Global", "Valor Anual", "Valor Mensal", "Jan", "Fev", "Mar", 
                           "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total Anual", "Reforço/Remanejamento"]
        for col in colunas_valores:
            df[col] = df[col].apply(converter_monetario)
        
        # Adicionando a coluna de fonte (nome do arquivo)
        df = preencher_valor_anual_proporcional(df, ano_referencia=2025)
        df["Fonte"] = file_name
        
        # Concatenar dados
        df_combinado = pd.concat([df_combinado, df], ignore_index=True)

        # Processamento complementar
        coluna_contrato = df_comple.columns[2]  # Coluna de contrato
        df_comple["É Complementar"] = df_comple[coluna_contrato].isna()
        df_comple[coluna_contrato] = df_comple[coluna_contrato].ffill()
        # Renomeando colunas para facilitar
        df_comple.columns = ["Regiao", "Processo", "Contrato", "Objeto", "Nota Empenho", "Valor Empenhado", "Valor Pago", "Valor Global", "Valor Anual", "Valor Mensal", "Status", "Ultima Repactuacao","Ocorrência","Data de Ocorrência", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total Anual", "Indice", "Evolucao", "Reajuste", "Reforço/Remanejamento","É Complementar"]
        
        # Convertendo valores financeiros
        colunas_valores = ["Valor Empenhado", "Valor Pago", "Valor Global", "Valor Anual", "Valor Mensal", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total Anual", "Reforço/Remanejamento"]
        for col in colunas_valores:
            # Aplicar a função nas colunas de interesse
            df_comple[col] = df_comple[col].apply(converter_monetario)

        df_comple["Fonte"] = file_name  # Adiciona uma coluna com o nome do arquivo
        df_combinado_1 = pd.concat([df_combinado_1, df_comple], ignore_index=True)
        

        # Salvar os resultados
        df_combinado.to_parquet("dados_combinados.parquet", index=False)
        df_combinado_1.to_parquet("dados_complementares.parquet", index=False)

    for arquivo in arquivos_download:
        file_id = arquivo["id"]
        excluir_arquivo(file_id)

    return df_combinado, df_combinado_1

#baixaar planilha que tem a evolução do empenho
def visualizar_empenhos_unicos():
    arquivos = [
    {"id": "1ff7-LmysSbjwGTUC0OiK4jQJP8NkHaY1", "name": "relatorio evolucao mes a mes.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ]# Lê o primeiro arquivo CSV baixado
   
    arquivos_download = baixar_arquivos_google_drive(arquivos)

    df_raw = pd.read_csv(arquivos_download[0]["conteudo"], sep=",", skiprows=2)  # CSV convertido
    print(df_raw)
    # Define meses e tipos
    meses = ["JAN/2025", "FEV/2025", "MAR/2025", "ABR/2025"]
    tipos = [
        "DESPESAS EMPENHADAS (CONTROLE EMPENHO)",
        "DESPESAS EMPENHADAS A LIQUIDAR (CONTROLE EMP)",
        "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)"
    ]

    dados = []
    for _, row in df_raw.iterrows():
        nota = row.get("Unnamed: 0")
        favorecido = row.get("Unnamed: 2")  # Nome pode variar conforme a planilha

        for mes in meses:
            for i, tipo in enumerate(tipos):
                col_index = 3 + meses.index(mes) * 3 + i
                if col_index < len(row):
                    valor = row.iloc[col_index]

                    if isinstance(valor, str):
                        valor = valor.replace('.', '').replace(',', '.')
                    try:
                        valor = float(valor)
                    except:
                        valor = 0.0

                    dados.append({
                        "Nota de Empenho": nota,
                        "Favorecido": favorecido,
                        "Mês": mes,
                        "Tipo de Métrica": tipo,
                        "Valor (R$)": valor
                    })

    df = pd.DataFrame(dados)
   
    
    df.to_parquet("dados_empenhos_evolucao.parquet", index=False)
    
    for arquivo in arquivos_download:
            file_id = arquivo["id"]
            excluir_arquivo(file_id)
        
    return df






def salvar_hora_atualizacao():
    with open("ultima_atualizacao.json", "w") as f:
        json.dump({"ultima_atualizacao": time.strftime('%Y-%m-%d %H:%M:%S')}, f)


def carregar_hora_atualizacao():
    try:
        if os.path.exists("ultima_atualizacao.json"):
            with open("ultima_atualizacao.json", "r") as f:
                data = json.load(f)
                return data.get("ultima_atualizacao")
    except:
        pass
    return None

def carregar_dados_salvos():
    try:
        if os.path.exists("dados_combinados.parquet") and os.path.exists("dados_complementares.parquet") and os.path.exists("dados_empenhos_evolucao.parquet"):
            df_principal = pd.read_parquet("dados_combinados.parquet")
            df_complementar = pd.read_parquet("dados_complementares.parquet")
            df_evolucao_empenho = pd.read_parquet("dados_empenhos_evolucao.parquet")
            return {
                "principal": df_principal,
                "complementar": df_complementar,
                "evolucao": df_evolucao_empenho
            }
    except Exception as e:
        st.warning(f"Erro ao carregar dados salvos: {e}")
    return None


# Verificar se os dados já estão salvos no session_state
if "dados" not in st.session_state:
    st.session_state.dados = carregar_dados_salvos()
if "ultima_atualizacao" not in st.session_state:
    st.session_state.ultima_atualizacao = carregar_hora_atualizacao()
    

# Função para processar e salvar os dados no session_state
#def processar_dados():
#    st.session_state.dados = baixar_arquivos_csv(PASTA_ID)  # Chama a função para baixar e processar os dados
#    st.session_state.ultima_atualizacao = time.strftime('%Y-%m-%d %H:%M:%S')  # Armazenar a hora da última atualização
#    st.success("📝 Dados carregados e salvos na memória.")

# Função para formatar os valores como R$ (Reais)
def formatar_real(valor):
    if pd.isna(valor): return ""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def aplicar_formatacao_moeda(df, colunas):
    for col in colunas:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^\d,]", "", regex=True).str.replace(",", "."),
            errors="coerce"
        )
    return df

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
            df_principal, df_complementar = processar_dados_principais_csv()
            df_evolucao_empenho = visualizar_empenhos_unicos()
            
            # Armazena os dois DataFrames separadamente no session_state
            st.session_state.dados = {
                "principal": df_principal,
                "complementar": df_complementar,
                "evolucao": df_evolucao_empenho
            }
            st.session_state.ultima_atualizacao = time.strftime('%Y-%m-%d %H:%M:%S')
            salvar_hora_atualizacao()
            st.success("✅ Dados atualizados!")  # Atualiza os dados quando o botão for pressionado

# Verificar se os dados estão carregados no session_state
if st.session_state.dados is not None:
    df_local = st.session_state.dados["principal"]
    df_complementares = st.session_state.dados["complementar"]
    df_evolucao_empenho = st.session_state.dados["evolucao"]
    
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
            col1.metric("💰 Valor Anual", formatar_real(df_local['Valor Anual Proporcional'].sum()))
            col2.metric("💰 Valor Empenhado", formatar_real(df_local['Valor Empenhado'].sum()))
            col3.metric("💵 Valor Pago", formatar_real(df_local['Valor Pago'].sum()))
            with col4:
                # Cálculo da diferença entre o valor anual e o valor empenhado
                df_local['Diferença'] = df_local['Valor Empenhado'] - df_local['Valor Anual Proporcional']

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
            

            col1, col2 = st.columns([1, 1])

            with col1:
                st.subheader(f"📄 Detalhes do Contrato: {contrato}")
                
                # Exibir informações do contrato
                contrato_info = df_local[df_local["Contrato"] == contrato].iloc[0]
                contrato_info_perc = df_contrato[df_contrato["Contrato"] == contrato].iloc[0]

                st.markdown(
                    f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 12px; box-shadow: 0px 2px 8px rgba(0,0,0,0.05); margin-bottom: 20px;">
                        <p><strong>📍 Região:</strong> {contrato_info['Regiao']}</p>
                        <p><strong>📦 Objeto:</strong> {contrato_info['Objeto']}</p>
                        <p><strong>💸 Valor Mensal:</strong> {formatar_real(contrato_info['Valor Mensal'])}</p>
                        <p><strong>🔄 Status Repactuação/Reajuste:</strong> {contrato_info['Status']}</p>
                        <hr>
                        <p><strong>📊 Execução do Valor Anual:</strong> {contrato_info_perc['Execucao Percentual (Anual)']:.2f}%</p>
                        <p><strong>📊 Execução do Valor Empenhado:</strong> {contrato_info_perc['Execucao Percentual (Empenhado)']:.2f}%</p>
                        <p><strong>📉 Percentual Faltante de Empenho:</strong> {contrato_info_perc['Percentual Faltante de Empenho']:.2f}%</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                dados_complementares = df_complementares[(df_complementares["É Complementar"] == True) & (df_complementares["Contrato"] == contrato)]
                notas_acumulado=[]
                if not dados_complementares.empty:
                    with st.expander("🔍 Unidades Vinculadas / Dados Complementares"):
                        st.markdown("Esses dados representam unidades vinculadas ao contrato selecionado:")

                        for _, row in dados_complementares.iterrows():
                            regiao = row["Regiao"]
                            objeto = row["Objeto"]
                            nota = row["Nota Empenho"]
                            valor_empenhado = formatar_real(row["Valor Empenhado"])
                            valor_pago = formatar_real(row["Valor Pago"])
                            valor_mensal = formatar_real(row["Valor Mensal"])
                            notas_acumulado.append(nota)
                            col3, col4 = st.columns([3, 2])
                            with col3:
                                st.markdown(f"""
                                    <div style="background-color: #eef2f7; padding: 12px; border-radius: 10px; margin-bottom: 10px;">
                                        <h5 style="margin-bottom: 5px;">📍 {regiao}</h5>
                                        <p style="margin: 0;"><strong>Objeto:</strong> {objeto}</p>
                                        <p style="margin: 0;"><strong>Nota de Empenho:</strong> {nota}</p>
                                    </div>
                                """, unsafe_allow_html=True)
                            with col4:
                                st.markdown(f"""
                                    <div style="background-color: #e0f7e9; padding: 12px; border-radius: 10px; margin-bottom: 10px;">
                                        <p style="margin: 0;"><strong>💰 Empenhado:</strong> {valor_empenhado}</p>
                                        <p style="margin: 0;"><strong>✅ Pago:</strong> {valor_pago}</p>
                                        <p style="margin: 0;"><strong>📆 Valor Mensal:</strong> {valor_mensal}</p>
                                    </div>
                                """, unsafe_allow_html=True)
                
            with col2:
                st.subheader("📊 Comparativo Anual, Empenhado e Pago")

                fig_valores = px.bar(
                    x=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                    y=[contrato_info["Valor Anual"], contrato_info["Valor Empenhado"], contrato_info["Valor Pago"]],
                    labels={"x": "Tipo de Valor", "y": "Valor (R$)"},
                    color=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                    color_discrete_map={
                        "Valor Anual": "#2ca02c",
                        "Valor Empenhado": "#1f77b4",
                        "Valor Pago": "#ff7f0e"
                    },
                    text=[formatar_real(contrato_info["Valor Anual"]),
                        formatar_real(contrato_info["Valor Empenhado"]),
                        formatar_real(contrato_info["Valor Pago"])]
                )

                fig_valores.update_layout(
                    height=400,
                    xaxis_title="Tipo de Valor",
                    yaxis_title="Valor (R$)",
                    showlegend=False,
                    bargap=0.25,
                    plot_bgcolor="#ffffff",
                    paper_bgcolor="#ffffff"
                )
                st.plotly_chart(fig_valores, use_container_width=True)

            # Gráfico mês a mês
            meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            df_melt = df_local.melt(id_vars=["Contrato", "Regiao"], value_vars=meses, var_name="Mês", value_name="Valor Pago Mensal")
            df_pagamento = df_melt.groupby(["Contrato", "Mês"], as_index=False)["Valor Pago Mensal"].sum()
            df_pagamento["Mês"] = pd.Categorical(df_pagamento["Mês"], categories=meses, ordered=True)
            df_pagamento = df_pagamento.sort_values("Mês")

            st.subheader("📆 Pagamentos Mensais por Contrato")
            fig_pagamento = px.bar(
                df_pagamento,
                x="Mês",
                y="Valor Pago Mensal",
                color="Contrato",
                labels={"Mês": "Mês", "Valor Pago Mensal": "Valor Pago (R$)"},
                barmode="group",
                
            )
            # Adicionar valores formatados nas barras
            for trace in fig_pagamento.data:
                trace.text = [formatar_real(val) for val in trace.y]
                trace.textposition = "outside"

            fig_pagamento.update_layout(
                height=500,
                xaxis_title="Mês",
                yaxis_title="Valor Pago (R$)",
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff"
            )

            st.plotly_chart(fig_pagamento, use_container_width=True)

            ### GRÁFICO DE EVOLUÇÃO MÊS A MÊS COM O VALOR ANUAL 
            valor_mensal_total = df_local["Valor Mensal"].sum()

            # Acumulado mês a mês do valor anual
            valor_anual_acumulado = [valor_mensal_total * (i + 1) for i in range(12)]

            # Agrupar total pago por mês (já está feito, só precisamos acumular)
            valores_pagos_mensais = df_pagamento.groupby("Mês")["Valor Pago Mensal"].sum().reindex(meses, fill_value=0)
            valores_pagos_acumulados = valores_pagos_mensais.cumsum().tolist()

            st.subheader("📈 Evolução Mês a Mês - Valor Anual vs. Valor Pago")

            # Opção para escolher o tipo de gráfico
            tipo_grafico = st.radio("Tipo de Gráfico", ["📊 Barras", "📈 Linha"], horizontal=True)

            # Calcular a evolução do valor anual proporcional acumulado por mês
            df_evolucao = df_local.copy()
            meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            df_evolucao_melt = df_evolucao.melt(id_vars=["Contrato"], value_vars=meses, var_name="Mês", value_name="Valor Pago Mensal")
            df_pagamento = df_evolucao_melt.groupby("Mês", as_index=False)["Valor Pago Mensal"].sum()
            df_pagamento["Mês"] = pd.Categorical(df_pagamento["Mês"], categories=meses, ordered=True)
            df_pagamento = df_pagamento.sort_values("Mês")
            df_pagamento["Valor Pago Acumulado"] = df_pagamento["Valor Pago Mensal"].cumsum()

            # Valor anual acumulado mês a mês
            valor_mensal_total = df_evolucao["Valor Mensal"].sum()
            df_pagamento["Valor Anual Acumulado"] = [(i + 1) * valor_mensal_total for i in range(len(df_pagamento))]

            # Criar gráfico dinâmico com base na seleção
            if tipo_grafico == "📊 Barras":
                fig = go.Figure()
                # Primeiro o Valor Anual Acumulado (fica à esquerda nas barras agrupadas)
                fig.add_trace(go.Bar(
                    x=df_pagamento["Mês"],
                    y=df_pagamento["Valor Anual Acumulado"],
                    name="Valor Anual Acumulado",
                    marker_color="#2ca02c",
                    text=[formatar_real(v) for v in df_pagamento["Valor Anual Acumulado"]],
                    textposition="outside"
                ))
                
                # Depois o Valor Pago (fica à direita)
                fig.add_trace(go.Bar(
                    x=df_pagamento["Mês"],
                    y=df_pagamento["Valor Pago Acumulado"],
                    name="Valor Pago",
                    marker_color="#1f77b4",
                    text=[formatar_real(v) for v in df_pagamento["Valor Pago Acumulado"]],
                    textposition="outside"
                ))
                
                fig.update_layout(barmode="group")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_pagamento["Mês"],
                    y=df_pagamento["Valor Pago Acumulado"],
                    mode='lines+markers',
                    name="Valor Pago Acumulado",
                    line=dict(color="#1f77b4", width=3),
                    fill='tozeroy',  # preenche do valor até o eixo X
                    fillcolor="rgba(31, 119, 180, 0.2)",
                    hovertemplate='<b>Valor Pago</b><br>Mês: %{x}<br>R$ %{y:,.2f}<extra></extra>'
                ))

                fig.add_trace(go.Scatter(
                    x=df_pagamento["Mês"],
                    y=df_pagamento["Valor Anual Acumulado"],
                    mode='lines+markers',
                    name="Valor Anual Acumulado",
                    line=dict(color="#2ca02c", width=3, dash='dash'),
                    fill='tonexty',  # empilha a área acima da anterior
                    fillcolor="rgba(44, 160, 44, 0.2)",
                    hovertemplate='<b>Valor Anual</b><br>Mês: %{x}<br>R$ %{y:,.2f}<extra></extra>'
                ))
                fig.update_traces(hovertemplate='%{customdata}')
                for trace in fig.data:
                    trace.customdata = [[
                        f"R$ {v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                    ] for v in trace.y]
                fig.update_layout(hovermode="x unified")
            # Layout padrão
            fig.update_layout(
                title="Evolução Mensal de Valores",
                xaxis_title="Mês",
                yaxis_title="Valor (R$)",
                height=500,
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
                
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
            )

            st.plotly_chart(fig, use_container_width=True)


            if pd.notna(contrato_info["Nota Empenho"]) and str(contrato_info["Nota Empenho"]).strip() != "":
                nota_filtrada = [str(contrato_info["Nota Empenho"]).strip()]
            else:           
                nota_filtrada = notas_acumulado

            # Caso haja mais de uma nota, gere os gráficos para cada uma
            for nota_item in nota_filtrada:
                # Filtra novamente para cada nota individualmente
                
                df_filtrado = df_evolucao_empenho[
                    df_evolucao_empenho["Nota de Empenho"].astype(str).str.contains(str(nota_item), na=False)
                ]

                df_resumo = df_filtrado.groupby(["Mês", "Tipo de Métrica"])["Valor (R$)"].sum().reset_index()
                df_pivot = df_resumo.pivot(index="Mês", columns="Tipo de Métrica", values="Valor (R$)").fillna(0)

                # Garante a ordem correta dos meses
                ordem_meses = ["JAN/2025", "FEV/2025", "MAR/2025", "ABR/2025"]
                df_pivot.index = pd.Categorical(df_pivot.index, categories=ordem_meses, ordered=True)
                df_pivot = df_pivot.sort_index()

                legenda_dict = {
                    "DESPESAS EMPENHADAS (CONTROLE EMPENHO)": 'Empenhado',
                    "DESPESAS EMPENHADAS A LIQUIDAR (CONTROLE EMP)": 'A Liquidar',
                    "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": 'Liquidado'
                }
                st.subheader(f"📈 Evolução Mês a Mês - Empenho x A liquidar x Liquidado - (Nota de Empenho: {nota_item})")

                # Opção para escolher o tipo de gráfico
                tipo_grafico_empenho = st.radio("Tipo de Gráfico", ["📊 Barras", "📈 Linha"], horizontal=True, key=f"grafico_empenho_{nota_item}")
                if tipo_grafico_empenho == "📊 Barras":
                    # Plota o gráfico de barras com a ordem correta
                    fig = go.Figure()
                    cores = {
                            
                            "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": "green",  # Cor verde para "Liquidado"
                        }
                    # Adiciona cada coluna de df_pivot como um conjunto de barras
                    for col in df_pivot.columns:
                        cor = cores.get(col)
                        fig.add_trace(go.Bar(
                            x=df_pivot.index,  # Meses como eixo X
                            y=df_pivot[col],  # Valores da métrica como eixo Y
                            name=legenda_dict.get(col, col),
                            text=[f"R$ {v:,.2f}" for v in df_pivot[col]],  # Formatação dos valores
                            textposition="outside",
                            marker_color=cor
                        ))

                        # Adicionar valores formatados nas barras
                    for trace in fig.data:
                        trace.text = [formatar_real(val) for val in trace.y]
                        trace.textposition = "outside"

                    # Atualiza o layout do gráfico de barras
                    fig.update_layout(
                        title=f"Evolução mês a mês — Nota de Empenho: {nota_item}",
                        xaxis_title="Mês",
                        yaxis_title="Valor (R$)",
                        barmode="group",  # Agrupar as barras
                        xaxis=dict(tickmode="array", tickvals=df_pivot.index),
                        xaxis_tickangle=-45,  # Angulo das labels do eixo X
                        height=500,
                        plot_bgcolor="#ffffff",
                        paper_bgcolor="#ffffff",
                        legend_title="Tipo de Métrica",
                    )

                    # Exibe o gráfico de barras no Streamlit
                    st.plotly_chart(fig, use_container_width=True, key=f"grafico_empenho_plotar_{nota_item}")
                else:
                    # Plota o gráfico de linha com a ordem correta
                    fig = go.Figure()
                    cores = {
                            "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": "green",  # Cor verde para "Liquidado"
                        }
                    # Adiciona cada coluna de df_pivot como uma linha
                    for col in df_pivot.columns:
                        cor = cores.get(col)
                        fig.add_trace(go.Scatter(
                            x=df_pivot.index,  # Meses como eixo X
                            y=df_pivot[col],  # Valores da métrica como eixo Y
                            mode='lines+markers',  # Linha com marcadores
                            name=legenda_dict.get(col, col),
                            line=dict(width=3, color=cor),
                            marker=dict(size=6),
                            text=[f"R$ {v:,.2f}" for v in df_pivot[col]],  # Formatação dos valores
                            hovertemplate='<b>' + legenda_dict.get(col, col) + '</b><br>Mês: %{x}<br>R$ %{y:,.2f}<extra></extra>'  # Corrigido aqui
                        ))
                    fig.update_traces(hovertemplate='%{customdata}')
                    for trace in fig.data:
                        trace.customdata = [[
                            f"R$ {v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                        ] for v in trace.y]
                    fig.update_layout(hovermode="x unified")

                    # Atualiza o layout do gráfico de linha
                    fig.update_layout(
                        title=f"Evolução mês a mês — Nota de Empenho: {nota_item}",
                        xaxis_title="Mês",
                        yaxis_title="Valor (R$)",
                        height=500,
                        plot_bgcolor="#ffffff",
                        paper_bgcolor="#ffffff",
                        legend_title="Tipo de Métrica",
                        xaxis=dict(tickmode="array", tickvals=df_pivot.index, showgrid=True),  # Ativa o grid no eixo X
                        yaxis=dict(showgrid=True),  # Ativa o grid no eixo Y
                        xaxis_tickangle=-45,
                    )

                    # Exibe o gráfico de linha no Streamlit
                    st.plotly_chart(fig, use_container_width=True)

           
           


    else:
        # Cálculo da diferença
        df_local['Diferença'] = df_local['Valor Empenhado'] - df_local['Valor Anual Proporcional']
        
        valor_anular = df_local[df_local['Diferença'] > 0]['Diferença'].sum()
        valor_reforcar = df_local[df_local['Diferença'] < 0]['Diferença'].sum()

        # Métricas principais
        col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 2, 2])
        col1.metric("Total de Contratos", len(df_local))
        col2.metric("💰 Valor Anual Total", formatar_real(df_local['Valor Anual'].sum()))
        col3.metric("💰 Valor Empenhado Total", formatar_real(df_local['Valor Empenhado'].sum()))
        col4.metric("💵 Valor Pago Total", formatar_real(df_local['Valor Pago'].sum()))

        with col5:
            if valor_reforcar < 0:
                st.metric("⚠️ Reforço Necessário", formatar_real(abs(valor_reforcar)), "Reforçar", delta_color="inverse")
            else:
                st.metric("✅ Valor a Anular", formatar_real(valor_anular), "Anular", delta_color="normal")

        # --- Tabs ---
        tab1, tab2 = st.tabs(["📌 Resumo Geral", "📉 Rescisões"])

        # ========== TAB 1 ==========
        with tab1:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 Comparação por Região")
                df_regiao = df_local.groupby("Regiao", as_index=False)[["Valor Anual", "Valor Empenhado", "Valor Pago"]].sum()
                df_regiao = df_regiao.sort_values(by="Valor Empenhado", ascending=False)

                fig = px.bar(
                    df_regiao,
                    x="Regiao",
                    y=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                    barmode="group",
                    title="💰 Comparação de Valores por Região",
                    color_discrete_map={
                        "Valor Anual": "#2ca02c",
                        "Valor Empenhado": "#1f77b4",
                        "Valor Pago": "#ff7f0e"
                    }
                )

                fig.update_layout(
                    xaxis_title="Região",
                    yaxis_title="Valor (R$)",
                    bargap=0.15,
                    height=500
                )

                for trace in fig.data:
                    trace.text = [formatar_real(v) for v in trace.y]

                st.plotly_chart(fig)

            with col2:
                st.subheader("📊 Comparação por Objeto")
                df_objeto = df_local.groupby("Fonte", as_index=False)[["Valor Anual", "Valor Empenhado", "Valor Pago"]].sum()
                df_objeto = df_objeto.sort_values(by="Valor Empenhado", ascending=False)

                fig_obj = px.bar(
                    df_objeto,
                    x="Fonte",
                    y=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                    barmode="group",
                    title="💰 Comparação de Valores por Objeto",
                    color_discrete_map={
                        "Valor Anual": "#2ca02c",
                        "Valor Empenhado": "#1f77b4",
                        "Valor Pago": "#ff7f0e"
                    }
                )

                limite = df_objeto[["Valor Anual", "Valor Empenhado", "Valor Pago"]].mean().mean()

                for trace in fig_obj.data:
                    trace.text = [formatar_real(val) for val in trace.y]
                    trace.textposition = ["outside" if val < limite else "inside" for val in trace.y]

                fig_obj.update_layout(
                    xaxis_title="Objeto",
                    yaxis_title="Valor (R$)",
                    bargap=0.15,
                    height=500
                )

                st.plotly_chart(fig_obj, use_container_width=True)

            # Destaque sobre contratos rescindidos
            rescisoes = df_local[df_local["Ocorrência"].str.lower() == "rescisão"].copy()
            rescisoes["Valor a Anular"] = rescisoes["Valor Empenhado"] - rescisoes["Valor Anual Proporcional"]
            valor_total_anular = rescisoes["Valor a Anular"].sum()

            st.markdown(f"""
            ### 💡 IMPORTANTE
            - **{len(rescisoes)} contratos rescindidos** foram identificados.
            - Valor total a anular: 🟢 **{formatar_real(valor_total_anular)}**
            > *Esse valor pode ser realocado ou economizado.*
            """)

        # ========== TAB 2 ==========
        with tab2:
            df_fmt = df_local.copy()
            df_fmt = aplicar_formatacao_moeda(df_fmt, ["Valor Empenhado", "Valor Pago", "Valor Anual Proporcional"])
            rescisoes["Valor a Anular"] = rescisoes["Valor Empenhado"] - rescisoes["Valor Anual Proporcional"]

            anular = rescisoes[rescisoes["Valor a Anular"] > 0]
            reforcar = rescisoes[rescisoes["Valor a Anular"] < 0]

            total_anular = anular["Valor a Anular"].sum()
            total_reforcar = reforcar["Valor a Anular"].sum()

            # --- Cards informativos ---
            st.markdown(f"""
            <style>
            .card-container {{
                display: flex;
                gap: 1rem;
                margin-top: 10px;
                margin-bottom: 5px;
            }}
            .card {{
                flex: 1;
                padding: 1rem;
                border-radius: 1rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                color: white;
                text-align: center;
                font-size: 1.2rem;
                font-weight: bold;
            }}
            .card.green {{
                background: linear-gradient(135deg, #2e7d32, #66bb6a);
            }}
            .card.red {{
                background: linear-gradient(135deg, #c62828, #ef5350);
            }}
            </style>
            <div class="card-container">
                <div class="card green">
                    ✅ Valor Passível de Anulação<br>
                    <span style="font-size: 1.6rem;">{formatar_real(total_anular)}</span>
                </div>
                <div class="card red">
                    ⚠️ Valor Necessário de Reforço<br>
                    <span style="font-size: 1.6rem;">{formatar_real(abs(total_reforcar))}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            
            # Função para gerar os cards lado a lado
            def mostrar_contratos_em_cards(dados, titulo="🔻 Contratos com valor a anular"):
                st.markdown(f"## {titulo}")
                num_colunas = 2  # Quantos cards por linha
                total_linhas = math.ceil(len(dados) / num_colunas)

                for i in range(total_linhas):
                    cols = st.columns(num_colunas)
                    for j in range(num_colunas):
                        idx = i * num_colunas + j
                        if idx < len(dados):
                            row = dados.iloc[idx]
                            with cols[j]:
                                st.markdown(f"""
                                <div style="
                                    background-color: #f1f8e9;
                                    border-left: 5px solid #558b2f;
                                    padding: 15px;
                                    border-radius: 12px;
                                    box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
                                    margin-bottom: 15px;
                                ">
                                    <h4 style="margin-top: 0;">📄 Contrato {row['Contrato']}</h4>
                                    <p><b>📍 Região:</b> {row['Regiao']}</p>
                                    <p><b>🎯 Objeto:</b> {row['Objeto']}</p>
                                    <p><b>💰 Valor Empenhado:</b> {formatar_real(row['Valor Empenhado'])}</p>
                                    <p><b>📊 Valor Anual:</b> {formatar_real(row['Valor Anual Proporcional'])}</p>
                                    <p style="color: green; font-size: 16px;"><b>🔻 Valor a Anular:</b> {formatar_real(row['Valor a Anular'])}</p>
                                </div>
                                """, unsafe_allow_html=True)

            # Exemplo de uso:
            mostrar_contratos_em_cards(anular)

            st.markdown("""
            <div style='margin-top: 10px; background-color: #e8f5e9; padding: 10px; border-left: 5px solid #2e7d32'>
            💡 Esses contratos apresentam saldo a ser devolvido devido à rescisão antecipada.
            </div>
            """, unsafe_allow_html=True)

            # --- Tabela: Reforço ---
            st.subheader("⚠️ Contratos que Excederam o Proporcional")
            reforcar_fmt = reforcar.copy()
            for col in ["Valor Empenhado", "Valor Anual Proporcional", "Valor a Anular"]:
                reforcar_fmt[col] = reforcar_fmt[col].apply(formatar_real)

            st.dataframe(
                reforcar_fmt[["Regiao", "Contrato", "Objeto", "Valor Empenhado", 
                            "Valor Anual Proporcional", "Valor a Anular", "Data de Ocorrência"]],
                use_container_width=True
            )

            st.markdown("""
            <div style='margin-top: 10px; background-color: #ffebee; padding: 10px; border-left: 5px solid #c62828'>
            ⚠️ Estes contratos consumiram mais do que o proporcional até a data da rescisão. Avaliar possível reforço ou erro no empenho.
            </div>
            """, unsafe_allow_html=True)

            # --- Exportação ---
            st.markdown("📥 Baixar dados filtrados:")
            csv = rescisoes.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button("⬇️ Baixar CSV com todos os dados filtrados", data=csv, file_name="contratos_rescindidos.csv", mime="text/csv")


else:
    st.warning("🚨 Nenhum dado carregado. Clique em 'Atualizar Dados' para baixar os dados.")
