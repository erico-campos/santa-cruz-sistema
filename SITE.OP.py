import sys
import os
import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, date
from io import BytesIO
import plotly.express as px



# --- 1. CORREÇÃO DE ACENTUAÇÃO E CODEC ---
if sys.stdout.encoding != 'UTF-8':
    try:
        import _locale
        _locale._getdefaultlocale = (lambda *args: ['pt_BR', 'UTF-8'])
    except:
        pass

# --- 2. IMPORTAÇÃO DO SUPABASE ---
try:
    from supabase import create_client, Client
except ImportError:
    st.error("🚨 Biblioteca 'supabase' não encontrada. Rode no terminal: pip install supabase")
    st.stop()

# --- 3. BIBLIOTECAS DE PDF ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# --- 4. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Santa Cruz Produção Master", layout="wide")

if not os.path.exists("anexos"):
    os.makedirs("anexos")

# --- 5. CONEXÃO COM SUPABASE ---
URL_SUPA = st.secrets["supabase"]["url"]
KEY_SUPA = st.secrets["supabase"]["key"]

@st.cache_resource
def conectar_supabase():
    return create_client(URL_SUPA, KEY_SUPA)

supabase = conectar_supabase()

# --- FUNÇÃO DE BUSCA DINÂMICA (MELHORADA) ---
def buscar_dados(tabela):
    try:
        # Busca todos os dados da tabela
        resposta = supabase.table(tabela).select("*").execute()
        return pd.DataFrame(resposta.data)
    except Exception as e:
        # Se a tabela ainda não existir, retorna DataFrame vazio sem travar o app
        return pd.DataFrame()

# --- 6. ESTADO DE SESSÃO (CORRIGIDO E COMPLETO) ---
if 'auth' not in st.session_state:
    st.session_state.update({
        'auth': False,
        'user_logado': "",
        'cargo_logado': "",
        'nivel': "USER",
        'id_user': "",
        'aba_atual': "dados_op", # Para controlar as 9 abas da Nova OP
        'edit_maq_id': None,      # Resolvendo o erro AttributeError
        'edit_usr_id': None,
        'edit_op_id': None,
        'abas_op': {
            "Dados da OP": True,
            "Dados do Cliente": True,
            "Especificações Técnicas": True,
            "Dados da Esteira": True,
            "Expedição": True,
            "Assistência Técnica": True,
            "Distribuição Interna": True,
            "Informações Adicionais": True
        }
    })

# Controle de edição para não perder o que está sendo digitado
if 'edit_op_id' not in st.session_state:
    st.session_state.edit_op_id = None

# --- 7. BANCO DE DADOS LOCAL (PARA BACKUP DE SEGURANÇA) ---
def iniciar_banco():
    with sqlite3.connect('fabrica_master.db') as db:
        cursor = db.cursor()
        # Tabela simplificada apenas para log local se necessário
        cursor.execute('''CREATE TABLE IF NOT EXISTS backup_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        evento TEXT, 
                        data_hora TEXT)''')
        db.commit()

iniciar_banco()


# --- FUNÇÕES PDF PROFISSIONAL (ADAPTADAS PARA 9 ABAS) ---

def gerar_pdf_relatorio_geral(df_relatorio):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1 * cm, leftMargin=1 * cm, topMargin=1 * cm,
                            bottomMargin=1 * cm)
    elementos = []
    styles = getSampleStyleSheet()

    estilo_celula = ParagraphStyle('CelTab', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    estilo_responsavel = ParagraphStyle('Resp', parent=styles['Normal'], fontSize=12, alignment=1, spaceAfter=20)

    # Cabeçalho
    responsavel = st.session_state.get('user_logado', 'Sistema')
    elementos.append(Paragraph("<b>MAPA GERAL DE PRODUÇÃO - SANTA CRUZ</b>", styles['Title']))
    elementos.append(
        Paragraph(f"Responsável: {responsavel} | Data: {datetime.now().strftime('%d/%m/%Y')}", estilo_responsavel))
    elementos.append(Spacer(1, 0.5 * cm))

    # Tabela de Dados
    dados_tabela = [[
        Paragraph("<b>Nº OP</b>", estilo_celula),
        Paragraph("<b>Cliente</b>", estilo_celula),
        Paragraph("<b>Máquina</b>", estilo_celula),
        Paragraph("<b>Líder</b>", estilo_celula),
        Paragraph("<b>Entrega</b>", estilo_celula),
        Paragraph("<b>Status</b>", estilo_celula)
    ]]

    for _, linha in df_relatorio.iterrows():
        dados_tabela.append([
            Paragraph(str(linha.get('numero_op', '')), estilo_celula),
            Paragraph(str(linha.get('cliente', '')), estilo_celula),
            Paragraph(str(linha.get('equipamento', '')), estilo_celula),
            Paragraph(str(linha.get('responsavel_setor', '')), estilo_celula),
            Paragraph(str(linha.get('data_entrega', '')), estilo_celula),
            Paragraph(f"{linha.get('progresso', 0)}%", estilo_celula)
        ])

    estilo_tab = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A242F")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])

    t = Table(dados_tabela, colWidths=[2.2 * cm, 5.8 * cm, 4.0 * cm, 3.5 * cm, 2.0 * cm, 1.5 * cm])
    t.setStyle(estilo_tab)
    elementos.append(t)
    doc.build(elementos)
    return buffer.getvalue()


def gerar_pdf_op(op_raw):
    # Trata nulos e garante dicionário
    op = {k: (v if pd.notna(v) else "") for k, v in dict(op_raw).items()}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=1.5 * cm)
    elementos = []
    styles = getSampleStyleSheet()

    # --- SEUS ESTILOS ORIGINAIS MANTIDOS ---
    cor_santa_cruz = colors.HexColor("#1A242F")
    estilo_secao = ParagraphStyle('Secao', parent=styles['Heading2'], textColor=colors.whitesmoke,
                                  backColor=cor_santa_cruz, leftIndent=5, fontSize=12, spaceBefore=10, spaceAfter=5)
    estilo_item = ParagraphStyle('Item', parent=styles['Normal'], fontSize=10, leading=12)

    # --- TÍTULO E CABEÇALHO ---
    elementos.append(Paragraph(f"ORDEM DE PRODUÇÃO: {op.get('numero_op', 'N/A')}", styles['Title']))
    elementos.append(Paragraph(f"<b>CLIENTE:</b> {op.get('cliente', 'N/A')}", styles['Normal']))
    elementos.append(Paragraph(f"<b>EQUIPAMENTO:</b> {op.get('equipamento', 'N/A')}", styles['Normal']))
    elementos.append(Spacer(1, 0.5 * cm))

    # --- NOVA LÓGICA PARA LER OS DADOS DINÂMICOS MANTENDO SEU LAYOUT ---
    dados_totais = op.get('especificacoes', {})
    if isinstance(dados_totais, str):
        try:
            dados_totais = json.loads(dados_totais)
        except:
            dados_totais = {}

    estrutura = dados_totais.get('estrutura', {})
    valores = dados_totais.get('valores', {})

    # Percorremos os módulos (abas) que você criou dinamicamente
    for titulo_aba, campos in estrutura.items():
        elementos.append(Paragraph(f" {titulo_aba.upper()}", estilo_secao))

        data_row = []
        temp_row = []

        for campo in campos:
            # Recupera o valor preenchido para este campo
            key_val = f"input_{titulo_aba}_{campo}"
            valor = valores.get(key_val, "")

            # Monta a célula com o seu estilo original
            temp_row.append(Paragraph(f"<b>{campo}:</b> {valor}", estilo_item))

            # Mantém sua lógica de 2 colunas por linha na tabela
            if len(temp_row) == 2:
                data_row.append(temp_row)
                temp_row = []

        # Se sobrar um campo sozinho no final da aba
        if temp_row:
            temp_row.append(Paragraph("", estilo_item))
            data_row.append(temp_row)

        if data_row:
            t = Table(data_row, colWidths=[9 * cm, 9 * cm])
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            elementos.append(t)
            elementos.append(Spacer(1, 0.3 * cm))

    doc.build(elementos)
    return buffer.getvalue()


# --- BLOCO DE LOGIN COM CONSULTA AO SUPABASE ---
if not st.session_state.auth:
    st.title("🏭 ERP Santa Cruz - Sistema de Gestão")

    with st.container(border=True):
        u_login = st.text_input("Usuário / Login").strip()
        p_senha = st.text_input("Senha", type="password")

        if st.button("Entrar no Sistema", use_container_width=True):
            # 1. Login Mestre (Backup de segurança)
            if u_login == "admsantacruz" and p_senha == "sc2024":
                st.session_state.update({
                    "auth": True, "nivel": "ADM",
                    "user_logado": "Administrador", "cargo_logado": "ADM"
                })
                st.rerun()

            # 2. Consulta real no Supabase
            try:
                res = supabase.table("usuarios").select("*").eq("usuario", u_login).eq("senha", p_senha).eq("ativo",
                                                                                                            1).execute()

                if res.data:
                    user = res.data[0]
                    cargo_bd = str(user['cargo']).upper()
                    nivel_bd = str(user['nivel']).upper()

                    # Lógica de Nível (Prioridade para ADM e PCP)
                    if "ADM" in cargo_bd or "PCP" in cargo_bd or nivel_bd == "ADM":
                        nivel_final = "ADM"
                    elif nivel_bd == "LIDER":
                        nivel_final = "LIDER"
                    elif nivel_bd == "VENDAS":
                        nivel_final = "VENDEDOR"
                    elif nivel_bd == "CLIENTE":
                        nivel_final = "CLIENTE"
                    else:
                        nivel_final = "USER"

                    st.session_state.update({
                        "auth": True,
                        "user_logado": user['nome'],
                        "cargo_logado": cargo_bd,
                        "id_user": user['usuario'],
                        "nivel": nivel_final
                    })
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos, ou cadastro inativo.")
            except Exception as e:
                st.error(f"Erro ao conectar com o servidor de usuários: {e}")

    st.stop()

# --- LÓGICA DE SIDEBAR E FILTROS DE ACESSO ---
with st.sidebar:
    st.title("Santa Cruz Automação")

    cargo = st.session_state.cargo_logado
    nivel = st.session_state.nivel

    # Inicialização das opções conforme o seu plano:
    if nivel == "ADM":
        opcoes = ["📊 Relatório", "📋 Lista de OPs", "➕ Nova OP", "⚙️ Configurações"]

    elif nivel == "VENDEDOR":
        # Vendedor pode ver suas OPs, Relatórios e Criar novas
        opcoes = ["📋 Lista de OPs", "📊 Relatório", "➕ Nova OP"]

    elif nivel == "LIDER":
        # Líder vê as OPs dele e Relatórios da sua produção
        opcoes = ["📋 Lista de OPs", "📊 Relatório"]

    elif nivel == "CLIENTE":
        # Cliente só acessa a lista para ver a sua própria OP
        opcoes = ["📋 Lista de OPs"]

    else:
        # Usuário comum (ex: montagem básica)
        opcoes = ["📋 Lista de OPs", "➕ Nova OP"]

    menu = st.radio("Ir para:", opcoes)

    st.divider()
    st.markdown(f"👤 **{st.session_state.user_logado}**")
    st.caption(f"🛠️ Setor: {cargo}")

    if st.button("Sair / Logout"):
        st.session_state.auth = False
        st.rerun()


# --- PÁGINA DE CONFIGURAÇÕES COMPLETA (INDENTAÇÃO CORRIGIDA) ---
if menu == "⚙️ Configurações":
    # Trava de Segurança: Apenas nível ADM acessa
    if st.session_state.nivel != "ADM":
        st.error("🚫 Acesso restrito ao Administrador.")
        st.stop()

    st.header("⚙️ Gestão Administrativa - Santa Cruz")

    # Criando as 3 abas
    t1, t2, t3 = st.tabs(["🏗️ Máquinas e Modelos", "🔑 Equipe Interna", "👤 Clientes"])

    # --- ABA 1: MÁQUINAS E CHECKLISTS ---
    with t1:
        st.subheader("Gerenciar Máquinas e Periféricos Padrão")
        df_m = buscar_dados("maquinas")

        val_n, val_c = "", ""
        if st.session_state.get('edit_maq_id'):
            if not df_m.empty and 'id' in df_m.columns:
                row = df_m[df_m['id'] == st.session_state.edit_maq_id]
                if not row.empty:
                    val_n = row.iloc[0]['nome_maquina']
                    val_c = row.iloc[0]['perifericos']

        with st.form("fm_maq"):
            n = st.text_input("Nome da Máquina", value=val_n)
            c = st.text_area("Periféricos / Peças Padrão (Separe por vírgula)", value=val_c)
            c_m1, c_m2 = st.columns(2)

            if c_m1.form_submit_button("💾 SALVAR NO SUPABASE"):
                if n:
                    dados = {"nome_maquina": n.upper(), "perifericos": c}
                    if st.session_state.get('edit_maq_id'):
                        dados["id"] = st.session_state.edit_maq_id
                    supabase.table("maquinas").upsert(dados).execute()
                    st.session_state.edit_maq_id = None
                    st.success("Máquina atualizada!")
                    st.rerun()

            if c_m2.form_submit_button("➕ NOVO / LIMPAR"):
                st.session_state.edit_maq_id = None
                st.rerun()

        if not df_m.empty:
            for _, m in df_m.iterrows():
                m_id = m.get('id')
                with st.container(border=True):
                    col1, col2, col3 = st.columns([4, 1, 1])
                    col1.write(f"**{m.get('nome_maquina', '---')}**")
                    if col2.button("✏️", key=f"ed_m_{m_id}"):
                        st.session_state.edit_maq_id = m_id
                        st.rerun()
                    if col3.button("🗑️", key=f"de_m_{m_id}"):
                        supabase.table("maquinas").delete().eq("id", m_id).execute()
                        st.rerun()

    # --- ABA 2: ACESSOS DA EQUIPE ---
    with t2:
        st.subheader("🔑 Controle de Usuários e Acessos")
        df_u = buscar_dados("usuarios")

        user_to_edit = {"usuario": "", "nome": "", "cargo": "", "nivel": "USER"}

        if st.session_state.get('edit_usr_id') and not df_u.empty:
            row_edit = df_u[df_u['id'] == st.session_state.edit_usr_id]
            if not row_edit.empty:
                user_to_edit["usuario"] = str(row_edit.iloc[0].get('usuario', ''))
                user_to_edit["nome"] = str(row_edit.iloc[0].get('nome', ''))
                user_to_edit["cargo"] = str(row_edit.iloc[0].get('cargo', ''))
                user_to_edit["nivel"] = str(row_edit.iloc[0].get('nivel', 'USER'))
                st.warning(f"📝 Editando: {user_to_edit['nome']}")

        with st.form("form_usuarios_erp", clear_on_submit=False):
            col_a, col_b = st.columns(2)
            u_login = col_a.text_input("Login / ID de Acesso", value=user_to_edit["usuario"])
            u_nome = col_b.text_input("Nome Completo", value=user_to_edit["nome"])
            u_senha = st.text_input("Senha", type="password")
            col_c, col_d = st.columns(2)
            u_cargo = col_c.text_input("Cargo / Setor", value=user_to_edit["cargo"])
            niveis_lista = ["ADM", "LIDER", "VENDEDOR", "USER"]
            idx_nivel = niveis_lista.index(user_to_edit["nivel"]) if user_to_edit["nivel"] in niveis_lista else 3
            u_nivel = col_d.selectbox("Nível de Permissão", niveis_lista, index=idx_nivel)

            col_btn_save, col_btn_cancel = st.columns(2)
            if col_btn_save.form_submit_button("💾 SALVAR"):
                if u_login and u_nome:
                    dados_u = {"usuario": u_login, "nome": u_nome, "cargo": u_cargo.upper(), "nivel": u_nivel, "ativo": 1}
                    if u_senha: dados_u["senha"] = u_senha
                    if st.session_state.get('edit_usr_id'): dados_u["id"] = st.session_state.edit_usr_id
                    supabase.table("usuarios").upsert(dados_u).execute()
                    st.session_state.edit_usr_id = None
                    st.success("Salvo com sucesso!")
                    st.rerun()
            if col_btn_cancel.form_submit_button("➕ NOVO"):
                st.session_state.edit_usr_id = None
                st.rerun()

        st.divider()
        if not df_u.empty:
            df_u = df_u.sort_values(by='nome')
            for _, u in df_u.iterrows():
                u_id = u.get('id')
                if u.get('usuario') != "admsantacruz":
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([2, 1.5, 0.5, 0.5])
                        c1.write(f"👤 **{u.get('nome', '---')}**")
                        c2.write(f"🏷️ {u.get('nivel', '---')}")
                        if c3.button("✏️", key=f"ed_u_{u_id}"):
                            st.session_state.edit_usr_id = u_id
                            st.rerun()
                        if c4.button("🗑️", key=f"de_u_{u_id}"):
                            supabase.table("usuarios").delete().eq("id", u_id).execute()
                            st.rerun()

    # --- ABA 3: GESTÃO DE CLIENTES ---
    with t3:
        st.subheader("👤 Cadastro de Clientes")
        st.caption("Estes clientes aparecerão na seleção da Nova OP.")

        with st.form("form_cliente_novo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n_cli = c1.text_input("Nome do Cliente / Empresa")
            cnpj_cli = c2.text_input("CNPJ / CPF")
            end_cli = st.text_input("Endereço de Entrega")

            if st.form_submit_button("💾 Salvar Cliente"):
                if n_cli:
                    try:
                        dados_cliente = {
                            "nome": n_cli.upper(),
                            "cnpj": cnpj_cli if cnpj_cli else "",
                            "endereco": end_cli if end_cli else ""
                        }
                        supabase.table("clientes").insert(dados_cliente).execute()
                        st.success(f"✅ Cliente {n_cli.upper()} cadastrado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro técnico ao salvar: {e}")
                else:
                    st.warning("O nome do cliente é obrigatório.")

        st.divider()
        try:
            df_cli = buscar_dados("clientes")
            if not df_cli.empty:
                for _, cli in df_cli.iterrows():
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                        nome_exibir = cli.get('nome', 'Sem Nome')
                        cnpj_exibir = cli.get('cnpj', '---')
                        col1.write(f"🏢 **{nome_exibir}** | CNPJ: {cnpj_exibir}")

                        if col2.button("🗑️", key=f"del_cli_{cli.get('id')}"):
                            supabase.table("clientes").delete().eq("id", cli.get('id')).execute()
                            st.rerun()
        except:
            st.info("Ainda não há clientes cadastrados.")

# --- PÁGINA: NOVA OP (VERSÃO COMPLETA E PROTEGIDA) ---
if menu == "➕ Nova OP":
    # 1. BUSCA DADOS DE APOIO
    df_maquinas = buscar_dados("maquinas")
    df_usuarios = buscar_dados("usuarios")
    df_clientes_db = buscar_dados("clientes")

    # --- TRATAMENTO DE SEGURANÇA PARA LISTAS ---
    lista_clientes = []
    if not df_clientes_db.empty and 'nome' in df_clientes_db.columns:
        lista_clientes = sorted(df_clientes_db['nome'].unique().tolist())

    lista_vendedores = []
    if not df_usuarios.empty:
        cols_u = df_usuarios.columns.tolist()
        # Filtra vendedores se a coluna 'nivel' existir, senão pega todos para não travar
        if 'nivel' in cols_u and 'nome' in cols_u:
            lista_vendedores = df_usuarios[df_usuarios['nivel'] == 'VENDEDOR']['nome'].tolist()
        elif 'nome' in cols_u:
            lista_vendedores = df_usuarios['nome'].tolist()

    lista_modelos = []
    if not df_maquinas.empty and 'nome_maquina' in df_maquinas.columns:
        lista_modelos = sorted(df_maquinas['nome_maquina'].unique().tolist())

    st.title("📄 Ordem de Produção")
    st.caption("Configure a estrutura e preencha os dados técnicos da máquina.")

    # 2. INICIALIZAÇÃO DA BIBLIOTECA NO SESSION STATE
    if 'biblioteca' not in st.session_state:
        st.session_state.biblioteca = {
            "Dados da OP": ["N° Op", "Modelo da Máquina", "Cliente", "Data da Op", "Data de entrega", "Vendedor"],
            "Dados do Cliente": ["CNPJ", "Endereço"],
            "Especificação Técnica": ["Alimentação", "Frasco", "Produto", "Bicos", "Produção", "Material"],
            "Dados da Esteira": ["Material", "Altura", "Comprimento", "Largura", "Plataforma"],
            "Assistência Técnica": ["Instalação"],
            "Dados Expedição": ["Endereço", "Frete e Seguro", "Embalagem"],
            "Distribuição Interna": ["Vendedor", "Revisor", "PCP", "Projeto", "Elétrica", "Montagem"],
            "Informações Adicionais": ["Observações"]
        }

    # --- PASSO 1: CONFIGURAR ESTRUTURA ---
    with st.expander("🏗️ PASSO 1: Configurar Estrutura (Editar Campos)",
                     expanded=not st.session_state.get('op_configurada')):
        st.info("Aqui você pode adicionar, remover ou renomear campos antes de preencher.")

        for modulo in list(st.session_state.biblioteca.keys()):
            with st.container(border=True):
                col_mod1, col_mod2 = st.columns([4, 1])
                incluir = col_mod1.checkbox(f"📦 Módulo: **{modulo}**", value=True, key=f"check_{modulo}")

                if col_mod2.button(f"🗑️", key=f"del_mod_{modulo}"):
                    del st.session_state.biblioteca[modulo]
                    st.rerun()

                if incluir:
                    for i, campo in enumerate(st.session_state.biblioteca[modulo]):
                        c_edit1, c_edit2 = st.columns([5, 1])
                        st.session_state.biblioteca[modulo][i] = c_edit1.text_input(
                            f"Nome do Campo", value=campo, key=f"f_{modulo}_{i}_{campo}"
                        )
                        if c_edit2.button("❌", key=f"btn_del_{modulo}_{i}"):
                            st.session_state.biblioteca[modulo].pop(i)
                            st.rerun()

                    if st.button(f"➕ Adicionar Campo em {modulo}", key=f"add_{modulo}"):
                        st.session_state.biblioteca[modulo].append("Novo Campo")
                        st.rerun()

        if st.button("🚀 CONFIRMAR MODELO E IR PARA PREENCHIMENTO", type="primary", use_container_width=True):
            st.session_state.op_configurada = True
            st.rerun()

    # --- PASSO 2: PREENCHIMENTO ---
    if st.session_state.get('op_configurada'):
        st.divider()
        abas_ativas = list(st.session_state.biblioteca.keys())
        abas = st.tabs(abas_ativas)

        if 'valores_preenchidos' not in st.session_state:
            st.session_state.valores_preenchidos = {}

        for i, nome_aba in enumerate(abas_ativas):
            with abas[i]:
                st.subheader(f"Preenchimento: {nome_aba}")
                for campo in st.session_state.biblioteca[nome_aba]:
                    key_input = f"input_{nome_aba}_{campo}"

                    # Lógica de campos especiais (Selectboxes)
                    campo_lower = campo.lower()
                    if "modelo da máquina" in campo_lower or "equipamento" in campo_lower:
                        st.session_state.valores_preenchidos[key_input] = st.selectbox(
                            campo, ["Selecione..."] + lista_modelos, key=key_input
                        )
                    elif "cliente" in campo_lower and "endereço" not in campo_lower:
                        st.session_state.valores_preenchidos[key_input] = st.selectbox(
                            campo, ["Selecione..."] + lista_clientes, key=key_input
                        )
                    elif "vendedor" in campo_lower:
                        st.session_state.valores_preenchidos[key_input] = st.selectbox(
                            campo, ["Selecione..."] + lista_vendedores, key=key_input
                        )
                    elif "data" in campo_lower:
                        # Campo de texto para data (mantendo flexibilidade de string)
                        st.session_state.valores_preenchidos[key_input] = st.text_input(
                            campo, placeholder="DD/MM/AAAA", key=key_input
                        )
                    else:
                        st.session_state.valores_preenchidos[key_input] = st.text_input(campo, key=key_input)

        # --- BOTÃO SALVAR ---
        st.divider()
        c_salvar, c_limpar = st.columns([3, 1])

        if c_salvar.button("🚀 SALVAR ORDEM DE PRODUÇÃO", type="primary", use_container_width=True):
            # Identificação das colunas principais para busca rápida na lista
            n_op_f, maq_f, cli_f = "S/N", "N/A", "Não Informado"

            for k, v in st.session_state.valores_preenchidos.items():
                k_lower = k.lower()
                if "n° op" in k_lower: n_op_f = v
                if "modelo da máquina" in k_lower: maq_f = v
                if "cliente" in k_lower and "endereço" not in k_lower: cli_f = v

            dados_salvar = {
                "numero_op": n_op_f,
                "equipamento": maq_f,
                "cliente": cli_f,  # Salva na coluna principal para facilitar filtros
                "especificacoes": {
                    "estrutura": st.session_state.biblioteca,
                    "valores": st.session_state.valores_preenchidos
                },
                "status": "Pendente",
                "progresso": 0,
                "data_op": datetime.now().strftime('%d/%m/%Y')
            }

            try:
                supabase.table("ordens").upsert(dados_salvar, on_conflict="numero_op").execute()
                st.success(f"✅ Ordem de Produção {n_op_f} salva com sucesso!")
                st.balloons()
                # Limpa estados para a próxima
                st.session_state.op_configurada = False
                st.session_state.valores_preenchidos = {}
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")

        if c_limpar.button("🔄 Reiniciar Construtor", use_container_width=True):
            st.session_state.op_configurada = False
            st.session_state.valores_preenchidos = {}
            st.rerun()


# --- PÁGINA: LISTA DE OPs (VERSÃO COMPLETA E CORRIGIDA) ---
if menu == "📋 Lista de OPs":
    st.title("📋 Central de Ordens de Produção")

    # 1. Busca os dados no Supabase
    df = buscar_dados("ordens")

    if not df.empty:
        # Filtro de busca no topo
        busca = st.text_input("🔍 Localizar por OP, Cliente ou Máquina", placeholder="Digite para filtrar...")

        if busca:
            df = df[df.astype(str).apply(lambda x: busca.lower() in x.str.lower().values, axis=1)]

        st.divider()

        # 2. Loop principal de exibição das OPs
        for i, row in df.iterrows():
            op_id = row['numero_op']
            especs = row.get('especificacoes', {})
            valores = especs.get('valores', {}) if isinstance(especs, dict) else {}

            # --- LÓGICA DO TÍTULO INTELIGENTE (CLIENTE E DATA) ---
            cliente_v = ""
            data_ent_v = ""

            # Tenta busca direta pelos campos padrão
            cliente_v = valores.get("input_Dados da OP_Cliente") or valores.get("input_Dados da OP_cliente")
            data_ent_v = valores.get("input_Dados da OP_Data de entrega") or valores.get(
                "input_Dados da OP_Data de entrega")

            # Se não achou (por ter renomeado o campo), faz varredura com exclusão de 'endereço'
            if not cliente_v:
                for k, v in valores.items():
                    if "cliente" in k.lower() and "endereço" not in k.lower() and "vendedor" not in k.lower():
                        cliente_v = v
                        break

            if not data_ent_v:
                for k, v in valores.items():
                    if "entrega" in k.lower():
                        data_ent_v = v
                        break

            # Tratamento de textos vazios
            txt_cliente = f" | {cliente_v}" if cliente_v and str(cliente_v).lower() != 'none' else ""

            # --- LÓGICA DE CORES (URGÊNCIA) ---
            cor_alerta = "⚪"
            dias_texto = ""
            if data_ent_v:
                try:
                    dt_ent = datetime.strptime(data_ent_v, '%d/%m/%Y').date()
                    dias_restantes = (dt_ent - date.today()).days
                    if dias_restantes > 30:
                        cor_alerta = "🟢"
                        dias_texto = f"({dias_restantes} dias)"
                    elif 15 <= dias_restantes <= 30:
                        cor_alerta = "🟡"
                        dias_texto = f"({dias_restantes} dias)"
                    else:
                        cor_alerta = "🔴"
                        dias_texto = "(ATRASADA)" if dias_restantes < 0 else f"({dias_restantes} dias)"
                except:
                    cor_alerta = "⚪"

            # --- EXIBIÇÃO DO CARD (EXPANDER) ---
            with st.expander(
                    f"{cor_alerta} OP: {op_id}{txt_cliente} | 📦 {row['equipamento']} | 📅 {data_ent_v} {dias_texto}"):

                progresso = int(row.get('progresso', 0))
                st.write(f"**Status da Produção: {progresso}%**")
                st.progress(progresso / 100)

                # Abas internas da OP
                t1, t2, t3, t4 = st.tabs(["📄 Ficha Técnica", "✅ Checklist", "📁 Arquivos", "⚙️ Ações"])

                with t1:
                    col_btn1, col_btn2 = st.columns([1, 1])

                    # Botão Editar: Carrega os dados e avisa o usuário
                    if col_btn1.button(f"✏️ Editar Ordem {op_id}", key=f"edit_{op_id}"):
                        st.session_state.op_configurada = True
                        st.session_state.biblioteca = especs.get('estrutura', {})
                        st.session_state.valores_preenchidos = valores
                        st.session_state.editando_op_id = op_id
                        st.success(f"Dados da OP {op_id} carregados! Clique em 'Nova OP' para modificar.")

                    if col_btn2.button(f"📥 Gerar PDF {op_id}", key=f"pdf_{op_id}"):
                        pdf_bytes = gerar_pdf_op(row)
                        st.download_button("Clique para Baixar", pdf_bytes, f"OP_{op_id}.pdf", "application/pdf")

                    st.divider()
                    if valores:
                        c1, c2 = st.columns(2)
                        for idx, (campo, valor) in enumerate(valores.items()):
                            nome_campo = campo.replace("input_", "").split("_")[-1]
                            target = c1 if idx % 2 == 0 else c2
                            target.write(f"**{nome_campo}:** {valor}")

                with t2:
                    st.subheader("✅ Checklist de Montagem")

                    # 1. Identificação dos dados da OP
                    maquina_da_op = row.get('equipamento', '')
                    op_id_atual = row.get('numero_op')

                    # 2. RECUPERAÇÃO DO ESTADO SALVO (O "pulo do gato")
                    # Buscamos no JSON 'especificacoes' a lista de peças que já foram marcadas antes
                    especs_atuais = row.get('especificacoes', {})
                    if not isinstance(especs_atuais, dict): especs_atuais = {}

                    # Se não houver nada salvo, começa com uma lista vazia
                    pecas_concluidas_no_banco = especs_atuais.get('pecas_concluidas', [])

                    # 3. Busca a lista de todas as peças que a máquina deve ter (o padrão)
                    df_maq_ref = buscar_dados("maquinas")
                    lista_total_perifericos = []

                    if not df_maq_ref.empty and maquina_da_op:
                        maq_alvo = df_maq_ref[df_maq_ref['nome_maquina'] == maquina_da_op]
                        if not maq_alvo.empty:
                            p_raw = str(maq_alvo.iloc[0].get('perifericos', ''))
                            lista_total_perifericos = [p.strip() for p in p_raw.split(',') if p.strip()]

                    # 4. EXIBIÇÃO DO CHECKLIST
                    if lista_total_perifericos:
                        st.write(f"Peças da máquina: **{maquina_da_op}**")

                        # Criamos uma lista temporária para o que o usuário marcar agora
                        novas_marcacoes = []

                        for p in lista_total_perifericos:
                            # AQUI ESTÁ A LÓGICA: Se a peça 'p' está na lista do banco,
                            # o checkbox já inicia como TRUE (marcado)
                            esta_pronto = p in pecas_concluidas_no_banco

                            check = st.checkbox(p, value=esta_pronto, key=f"chk_{op_id_atual}_{p}")

                            # Se estiver marcado (pelo banco ou pelo clique agora), mostra o aviso verde
                            if check:
                                st.markdown(f"🟢 **{p}** - CONCLUÍDO", unsafe_allow_html=True)
                                novas_marcacoes.append(p)
                            else:
                                st.markdown(f"⚪ <span style='color:gray'>{p} - Pendente</span>", unsafe_allow_html=True)

                        st.divider()

                        # 5. BOTÃO PARA SALVAR
                        if st.button(f"💾 Salvar Progresso OP {op_id_atual}", key=f"btn_save_{op_id_atual}"):
                            total = len(lista_total_perifericos)
                            prontos = len(novas_marcacoes)
                            porcentagem = int((prontos / total) * 100)

                            # Atualizamos o JSON com a nova lista de peças marcadas
                            especs_atuais['pecas_concluidas'] = novas_marcacoes

                            try:
                                supabase.table("ordens").update({
                                    "progresso": porcentagem,
                                    "especificacoes": especs_atuais
                                }).eq("numero_op", op_id_atual).execute()

                                st.success(f"Salvo! {porcentagem}% concluído.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")
                    else:
                        st.warning("Nenhuma peça cadastrada para este modelo.")

                with t3:
                    st.subheader("Anexos e Documentos")
                    st.file_uploader("Subir fotos ou PDF", key=f"file_{op_id}")
                    st.caption("Nota: Para salvar permanentemente, é necessário configurar o Supabase Storage.")

                with t4:
                    st.subheader("Controle Administrativo")
                    if st.button(f"🗑️ Deletar Ordem {op_id}", key=f"del_{op_id}"):
                        if st.warning("Deseja mesmo excluir?"):
                            supabase.table("ordens").delete().eq("numero_op", op_id).execute()
                            st.rerun()
    else:
        st.info("Nenhuma Ordem de Produção encontrada.")

# --- PÁGINA: RELATÓRIO (LÓGICA ESTRUTURA E GRÁFICOS) ---
elif menu == "📊 Relatório":
    st.header("📊 Dashboard de Produção Santa Cruz")

    # 1. Busca dados do Supabase
    df_rel = buscar_dados("ordens")

    if not df_rel.empty:
        # Tratamento de dados
        df_rel['progresso'] = pd.to_numeric(df_rel['progresso'], errors='coerce').fillna(0)

        # --- FILTRO DE "ESTRUTURA" (O que você pediu) ---
        # Só mostra no relatório o que ainda está em fase de estrutura/montagem (Progresso < 100)
        df_ativa = df_rel[df_rel['progresso'] < 100].copy()
        df_concluida = df_rel[df_rel['progresso'] == 100].copy()

        # --- VISÃO ADM / PCP (Gráficos) ---
        if st.session_state.nivel == "ADM" or "PCP" in st.session_state.cargo_logado:
            col_m1, col_m2 = st.columns(2)

            # Gráfico de Pizza: Geral
            total_ops = len(df_rel)
            fig_pizza = px.pie(
                values=[len(df_ativa), len(df_concluida)],
                names=['Em Andamento', 'Finalizadas'],
                title="Status Geral da Fábrica",
                hole=0.4,
                color_discrete_sequence=['#f39c12', '#27ae60']
            )
            col_m1.plotly_chart(fig_pizza, use_container_width=True)

            # Gráfico de Barras: Carga por Líder
            # Gráfico de Barras: Carga por Vendedor ou Equipamento
            # Mudamos 'responsavel_setor' para 'vendedor' que existe no seu banco
            fig_lider = px.bar(
                df_ativa,
                x='vendedor',
                y='progresso',
                title="Progresso por Vendedor (Carga Ativa)",
                color='vendedor',
                labels={'vendedor': 'Responsável', 'progresso': 'Progresso %'}
            )
            col_m2.plotly_chart(fig_lider, use_container_width=True)

        st.divider()

        # --- MAPA DE PRODUÇÃO ATIVA ---
        st.subheader("🏗️ OPs em Processo (Filtro: Estrutura Pendente)")

        if not df_ativa.empty:
            # Opção de PDF do Mapa Geral
            df_pdf = df_ativa.rename(columns={
                'numero_op': 'Nº OP', 'cliente': 'Cliente', 'equipamento': 'Máquina',
                'responsavel_setor': 'Líder', 'data_entrega': 'Entrega', 'progresso': 'Progresso %'
            })

            btn_pdf = st.download_button(
                label="📥 Gerar PDF do Mapa de Produção",
                data=gerar_pdf_relatorio_geral(df_pdf),
                file_name=f"MAPA_PRODUCAO_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

            # Tabela Visual
            st.dataframe(
                df_ativa[['numero_op', 'cliente', 'equipamento', 'vendedor', 'data_entrega', 'progresso']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ Nenhuma máquina pendente de estrutura no momento!")

    else:
        st.info("Sem dados para gerar relatórios.")














