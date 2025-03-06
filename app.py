import streamlit as st
from bs4 import BeautifulSoup
from unidecode import unidecode
import re
import pandas as pd
from io import BytesIO

# Dicionário de mapeamento entre cargos extraídos e os cargos da planilha
cargo_mapeamento = {
    'gestor': 'GESTOR TITULAR',
    'gestorsubstituto': 'GESTOR SUBSTITUTO',
    'fiscaladministrativo': 'FISCAL ADMINISTRATIVO',
    'fiscaladministrativosubstituto': 'FISCAL ADMINISTRATIVO SUBSTITUTO',
    'fiscaltecnico': 'FISCAL TÉCNICO',
    'fiscaltecnicosubstituto': 'FISCAL TÉCNICO SUBSTITUTO'
}

# Função para normalizar o texto (remover acentos, transformar para minúsculas, remover espaços extras e "(a)")
def normalizar_texto(texto):
    if texto:
        texto = unidecode(texto)  # Remove acentos
        texto = texto.lower()  # Transforma para minúsculas
        texto = re.sub(r'\s?\(a\)\s?', '', texto)  # Remove "(a)" e "(A)"
        texto = texto.strip()  # Remove espaços extras no início e fim
        texto = ' '.join(texto.split())  # Remove espaços extras no meio
        texto = texto.replace(" ", "")  # Remove espaços entre as palavras
    return texto

# Função para processar a tabela HTML e criar o dicionário de nomes e cargos
def processar_tabela_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.find_all('tr')
    dicionario_nomes_cargos = {
        'GESTOR TITULAR': '',
        'GESTOR SUBSTITUTO': '',
        'FISCAL ADMINISTRATIVO': '',
        'FISCAL ADMINISTRATIVO SUBSTITUTO': '',
        'FISCAL TÉCNICO': '',
        'FISCAL TÉCNICO SUBSTITUTO': ''
    }

    for row in rows[1:]:  # Começa da segunda linha, que contém os dados
        cells = row.find_all('td')
        try:
            if len(cells) >= 3:
                nome = cells[1].get_text(strip=True)
                cargo_extraido = cells[2].get_text(strip=True)
                cargo_normalizado = normalizar_texto(cargo_extraido)
                cargo = None
                for chave, valor in cargo_mapeamento.items():
                    if cargo_normalizado == chave:
                        cargo = valor
                        break
                if cargo:
                    dicionario_nomes_cargos[cargo] = nome
        except Exception as e:
            print(f"Erro ao processar a linha: {e}")
    
    return dicionario_nomes_cargos

# Função para normalizar a string para facilitar a comparação
def normalizar_string(s):
    return unidecode(s).lower() if isinstance(s, str) else s.lower()

# Função para normalizar toda a planilha
def normalizar_planilha(df):
    df_normalizado = df.apply(lambda x: normalizar_string(x) if isinstance(x, str) else x)
    return df_normalizado

# Função para buscar os dados de uma pessoa pelo nome
def buscar_dados(nome):
    nome = nome.strip()  # Remover espaços e normalizar
    nome_normalizado = normalizar_string(nome)  # Normalizar a string
    df_normalizado = normalizar_planilha(df)  # Normalizar a planilha
    for coluna in df_normalizado.columns:
        for idx, value in df_normalizado[coluna].items():
            if normalizar_string(str(value)) == nome_normalizado:
                dados_coluna = df.columns.get_loc(coluna) + 1
                return df_normalizado.iloc[idx, dados_coluna]
    return None

def atualizar_planilha(df, contrato, unidade, nomes_e_cargos):
    df_original = df.copy()
    erro_detectado = False  # Copiar a planilha original para comparações futuras
    linha_existente = df[(df['Nº CONTRATO'] == contrato) & (df['UNIDADE'] == unidade)]
    
    if not linha_existente.empty:
        # Se o contrato e a unidade existem, realiza as atualizações
        for cargo, novo_nome in nomes_e_cargos.items():
            dados_novos = buscar_dados(novo_nome)
            if dados_novos is not None:
                dados_coluna = df.columns.get_loc(cargo) + 1
                df.at[linha_existente.index[0], df.columns[dados_coluna]] = dados_novos
            else:
                dados_coluna = df.columns.get_loc(cargo) + 1
                df.at[linha_existente.index[0], df.columns[dados_coluna]] = ""
                st.warning(f"🚨 **Pessoa não localizada**: A pessoa '{novo_nome}' não foi encontrada. Você precisa atuar!")
        # Comparação de nome atual e novo
        for cargo, novo_nome in nomes_e_cargos.items():
            nome_atual = linha_existente.iloc[0, df.columns.get_loc(cargo)].strip()
            if nome_atual != novo_nome:
                df.at[linha_existente.index[0], cargo] = novo_nome
    else:
        # Caso o contrato exista mas a unidade não corresponda
        linha_contrato_existente = df[df['Nº CONTRATO'] == contrato]
        if not linha_contrato_existente.empty:
            st.warning("🚨 **Contrato já cadastrado**, mas a **unidade não confere**. Verifique a grafia da unidade.")
            erro_detectado = True
        else:
            # Caso o contrato e a unidade não existam, criar uma nova linha
            nova_linha = {'UNIDADE': unidade, 'Nº CONTRATO': contrato}
            for cargo, nome in nomes_e_cargos.items():
                nova_linha[cargo] = nome
                dados_novos = buscar_dados(nome)
                if dados_novos is not None:
                    dados_coluna = df.columns.get_loc(cargo) + 1
                    nova_linha[df.columns[dados_coluna]] = dados_novos
                else:
                    dados_coluna = df.columns.get_loc(cargo) + 1
                    nova_linha[df.columns[dados_coluna]] = ""
                    st.warning(f"🚨 **Pessoa não localizada**: A pessoa '{nome}' não foi encontrada. Você precisa atuar!")
            nova_linha_df = pd.DataFrame([nova_linha])
            df = pd.concat([df, nova_linha_df], ignore_index=True)
    
    return df, df_original, erro_detectado
# Função para gerar o arquivo Excel para download
def gerar_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output

# Função para carregar a planilha
def carregar_planilha(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)
        st.success("📊 Planilha carregada com sucesso!")
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar a planilha: {e}")
        return None

# Função para mostrar as diferenças entre antes e depois (somente as linhas alteradas)
def mostrar_diferencas(df_original, df_atualizado):
    # Encontrar as linhas alteradas
    linhas_alteradas = []
    for i in range(len(df_atualizado)):
        linha_original = df_original.iloc[i]
        linha_atualizada = df_atualizado.iloc[i]
        if not linha_original.equals(linha_atualizada):
            linhas_alteradas.append(i)
    
    # Se houver linhas alteradas, mostre as diferenças
    if linhas_alteradas:
        df_diff = pd.DataFrame(columns=df_atualizado.columns)
        detalhes_das_alteracoes = []
        for i in linhas_alteradas:
            row_diff = {}
            for col in df_atualizado.columns:
                if df_original[col].iloc[i] != df_atualizado[col].iloc[i]:
                    detalhes_das_alteracoes.append(
                        f"<span style='color: red;'>🔧 **Alterado em '{col}':** De <span style='color: blue;'>'{df_original[col].iloc[i]}'</span> → Para <span style='color: green;'>'{df_atualizado[col].iloc[i]}'</span></span>"
                    )
        return detalhes_das_alteracoes, df_atualizado.iloc[linhas_alteradas], df_original.iloc[linhas_alteradas]
    return None, None, None

# Streamlit interface
st.set_page_config(page_title="📝 Atualizador de Planilha", page_icon="📑", layout="wide")
st.title('📑 Atualização de Planilha a partir de HTML')
st.markdown("""
    **Bem-vindo ao atualizador de planilhas!**  
    Este aplicativo permite atualizar os dados de fiscais em uma planilha com base nas informações extraídas de uma tabela HTML.
    
    🛠️ **Passos:**  
    1. Carregue a planilha inicial.  
    2. Cole o código HTML da tabela.  
    3. Atualize a planilha e baixe o arquivo atualizado.
""", unsafe_allow_html=True)

# Upload da planilha
uploaded_file = st.file_uploader("📤 Carregue a Planilha (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = carregar_planilha(uploaded_file)
    
    # Entrada do HTML
    html_input = st.text_area("🔧 Cole o HTML da Tabela aqui:", height=300)

    if html_input:
        dicionario = processar_tabela_html(html_input)
        st.subheader("📋 Dicionário de Nomes e Cargos extraído do HTML:")
        st.write(dicionario)
        
        contrato = st.text_input("🔢 Número do contrato", value='00/2024')
        unidade = st.text_input("🏢 Unidade", value='ABC Paulista/SP')

        if st.button("📤 Atualizar Planilha"):
            df_atualizado, df_original, erro_detectado = atualizar_planilha(df, contrato, unidade, dicionario)

            if erro_detectado:
                st.warning("🚨 **Erro detectado**: O contrato já está registrado, mas a unidade não confere. Por favor, verifique.")
            else:
                st.success("✔️ Planilha atualizada com sucesso!")

                # Mostrar as diferenças entre a planilha original e a atualizada
                st.subheader("🔄 Diferenças - Linhas Alteradas:")
                detalhes, df_alteradas_atual, df_alteradas_original = mostrar_diferencas(df_original, df_atualizado)

                if detalhes:
                    st.write("🔧 **Alterações detectadas nas linhas:**")
                    for detalhe in detalhes:
                        st.markdown(detalhe, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("📝 Planilha Original - Linhas Alteradas")
                        st.dataframe(df_alteradas_original, use_container_width=True)

                    with col2:
                        st.subheader("🔄 Planilha Atualizada - Linhas Alteradas")
                        st.dataframe(df_alteradas_atual, use_container_width=True)

                else:
                    st.write("🔔 Não há alterações nas linhas.")

                # Adicionar botão de download
                excel_file = gerar_excel(df_atualizado)
                st.download_button(
                    label="💾 Baixar Planilha Atualizada",
                    data=excel_file,
                    file_name="planilha_atualizada.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
