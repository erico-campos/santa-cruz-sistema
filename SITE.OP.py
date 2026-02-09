import sys
import os

# --- 1. CORREÇÃO DE ACENTUAÇÃO E CODEC ---
if sys.stdout.encoding != 'UTF-8':
    try:
        import _locale
        _locale._getdefaultlocale = (lambda *args: ['pt_BR', 'UTF-8'])
    except:
        pass

import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, date
from io import BytesIO
import plotly.express as px

# --- 2. IMPORTAÇÃO DA CONEXÃO GOOGLE ---
try:
    from st_gsheets_connection import GSheetsConnection
except ImportError:
    try:
        from streamlit_gsheets import GSheetsConnection
    except ImportError:
        st.error("🚨 Biblioteca 'st-gsheets-connection' não encontrada no ambiente.")
        st.stop()

# --- 3. BIBLIOTECAS DE PDF ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

# --- 4. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Santa Cruz Produção Master", layout="wide")

if not os.path.exists("anexos"):
    os.makedirs("anexos")

# --- 5. CONEXÃO COM GOOGLE SHEETS ---
conn_sheets = st.connection("gsheets", type=GSheetsConnection)

# --- AJUSTE AQUI: Variável global para o nome da aba ---
# Após renomear na planilha, o código usará esta variável em todos os menus
NOME_ABA = "DADOS"

# --- 6. ESTADO DE SESSÃO (SESSION STATE) ---
for key in ['auth', 'user_logado', 'cargo_logado', 'nivel', 'layout_confirmado']:
    if key not in st.session_state:
        st.session_state[key] = False if key in ['auth', 'layout_confirmado'] else ""

if 'campos_dinamicos' not in st.session_state:
    st.session_state.campos_dinamicos = {}
if 'nomes_specs' not in st.session_state:
    st.session_state.nomes_specs = ["Alimentação", "Frascos", "Produto", "Bicos", "Produção", "Estrutura"]

for edit_key in ['edit_op_id', 'edit_lid_id', 'edit_usr_id', 'edit_maq_id']:
    if edit_key not in st.session_state:
        st.session_state[edit_key] = None

# --- 7. BANCO DE DADOS LOCAL ---
def iniciar_banco():
    with sqlite3.connect('fabrica_master.db') as db:
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ordens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, numero_op TEXT, equipamento TEXT, cliente TEXT, cnpj TEXT, 
                        data_op TEXT, vendedor TEXT, data_entrega TEXT, responsavel_setor TEXT, 
                        est_material TEXT, est_comprimento TEXT, est_altura TEXT, est_largura TEXT, est_plataforma TEXT,
                        dist_vendedor TEXT, dist_revisor TEXT, dist_pcp TEXT, dist_projeto TEXT, dist_eletrica TEXT, dist_montagem TEXT,
                        exp_endereco TEXT, ast_instalacao TEXT, info_adicionais_ficha TEXT DEFAULT "{}",
                        progresso INTEGER DEFAULT 0, checks_concluidos TEXT DEFAULT "", status TEXT DEFAULT 'Em Produção',
                        acompanhamento_log TEXT DEFAULT "[]", anexo TEXT)''')
        cursor.execute("CREATE TABLE IF NOT EXISTS maquinas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, conjuntos TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS setores (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")
        cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, senha TEXT, cargo TEXT, ativo INTEGER)")
        db.commit()

iniciar_banco()

# --- FUNÇÃO PDF PROFISSIONAL (REVISADA E CORRIGIDA) ---
def gerar_pdf_relatorio_geral(df_relatorio):
    buffer = BytesIO()
    # Configuração da Folha A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm
    )

    elementos = []
    styles = getSampleStyleSheet()

    # Estilo para o texto dentro das células
    estilo_celula = ParagraphStyle(
        'CelTab',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=1  # Centralizado
    )

    # Estilo para o título do responsável
    estilo_responsavel = ParagraphStyle(
        'Resp',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,
        spaceAfter=20
    )

    # --- CABEÇALHO DO RELATÓRIO ---
    responsavel = st.session_state.get('user_logado', 'Sistema')
    titulo = Paragraph("<b>MAPA GERAL DE PRODUÇÃO - SANTA CRUZ</b>", styles['Title'])
    sub_titulo = Paragraph(f"Responsável: {responsavel} | Data: {datetime.now().strftime('%d/%m/%Y')}",
                           estilo_responsavel)

    elementos.append(titulo)
    elementos.append(sub_titulo)
    elementos.append(Spacer(1, 0.5 * cm))

    # --- MONTAGEM DA TABELA ---
    dados_tabela = [[
        Paragraph("<b>Nº OP</b>", estilo_celula),
        Paragraph("<b>Cliente</b>", estilo_celula),
        Paragraph("<b>Máquina</b>", estilo_celula),
        Paragraph("<b>Líder</b>", estilo_celula),
        Paragraph("<b>Entrega</b>", estilo_celula),
        Paragraph("<b>Status</b>", estilo_celula)
    ]]

    # Conteúdo vindo do DataFrame (com tratamento para nomes de colunas)
    for _, linha in df_relatorio.iterrows():
        # Usamos .get() ou nomes convertidos para evitar erro de coluna ausente
        dados_tabela.append([
            Paragraph(str(linha.get('Nº OP', linha.get('numero_op', ''))), estilo_celula),
            Paragraph(str(linha.get('Cliente', linha.get('cliente', ''))), estilo_celula),
            Paragraph(str(linha.get('Máquina', linha.get('equipamento', ''))), estilo_celula),
            Paragraph(str(linha.get('Líder', linha.get('responsavel_setor', ''))), estilo_celula),
            Paragraph(str(linha.get('Entrega', linha.get('data_entrega', ''))), estilo_celula),
            Paragraph(f"{linha.get('Progresso %', linha.get('progresso', 0))}%", estilo_celula)
        ])

    # Estilo Visual da Tabela
    estilo_tab = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A242F")),  # Azul Marinho Santa Cruz
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    t = Table(dados_tabela, colWidths=[2.2 * cm, 5.8 * cm, 4.0 * cm, 3.5 * cm, 2.0 * cm, 1.5 * cm])
    t.setStyle(estilo_tab)
    elementos.append(t)

    # Rodapé
    elementos.append(Spacer(1, 1 * cm))
    elementos.append(
        Paragraph(f"<center><font size=8>Relatório gerado automaticamente pelo Sistema Santa Cruz</font></center>",
                  styles['Normal']))

    doc.build(elementos)
    return buffer.getvalue()


def gerar_pdf_op(op_raw):
    # Converte para dicionário e trata valores nulos para evitar erros de renderização
    op = {k: (v if pd.notna(v) else "") for k, v in dict(op_raw).items()}
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    elementos = []
    styles = getSampleStyleSheet()

    # --- CONFIGURAÇÃO DE ESTILOS ---
    cor_fundo_faixa = colors.HexColor("#1A242F")
    cor_borda = colors.HexColor("#BDC3C7")

    estilo_titulo_op = ParagraphStyle(
        'TituloOP', parent=styles['Heading1'], fontSize=22, alignment=1, spaceAfter=5, textColor=cor_fundo_faixa
    )

    estilo_sub_lider = ParagraphStyle(
        'SubLider', parent=styles['Normal'], fontSize=12, alignment=1, spaceAfter=20, textColor=colors.black
    )

    estilo_item = ParagraphStyle(
        'ItemTexto', parent=styles['Normal'], fontSize=11, leading=14
    )

    # --- INÍCIO DO CONTEÚDO ---
    # Título Principal: Número da OP
    elementos.append(Paragraph(f"ORDEM DE PRODUÇÃO: {op.get('numero_op', 'N/A')}", estilo_titulo_op))

    # Subtítulo: Líder Responsável
    lider_val = op.get('responsavel_setor') or "NÃO DEFINIDO"
    elementos.append(Paragraph(f"Líder Responsável: <b>{str(lider_val).upper()}</b>", estilo_sub_lider))

    elementos.append(Spacer(1, 0.5 * cm))

    # --- TABELA DE DADOS DO PROJETO ---
    # Verificamos se o equipamento e cliente existem para evitar textos vazios
    dados_p = [
        [Paragraph(f"<b>CLIENTE:</b><br/>{op.get('cliente', '')}", estilo_item),
         Paragraph(f"<b>EQUIPAMENTO:</b><br/>{op.get('equipamento', '')}", estilo_item)],
        [Paragraph(f"<b>CNPJ:</b><br/>{op.get('cnpj', '')}", estilo_item),
         Paragraph(f"<b>DATA ENTREGA:</b><br/>{op.get('data_entrega', '')}", estilo_item)]
    ]

    t1 = Table(dados_p, colWidths=[9 * cm, 9 * cm])
    t1.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, cor_borda),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(t1)
    elementos.append(Spacer(1, 0.8 * cm))

    # --- ESPECIFICAÇÕES TÉCNICAS (DINÂMICAS) ---
    elementos.append(
        Paragraph(f'<font color="white" backColor="{cor_fundo_faixa}"><b>  ESPECIFICAÇÕES TÉCNICAS</b></font>',
                  styles['Heading2']))

    try:
        # Tenta carregar o JSON. Se a célula estiver vazia ou inválida, gera dicionário vazio
        raw_specs = op.get('info_adicionais_ficha', '{}')
        specs = json.loads(raw_specs) if isinstance(raw_specs, str) and raw_specs.strip() else {}

        data_tec = []
        itens_temp = []
        for k, v in specs.items():
            itens_temp.append(Paragraph(f"<b>{k}:</b> {v}", estilo_item))
            if len(itens_temp) == 2:
                data_tec.append(itens_temp)
                itens_temp = []

        if itens_temp:
            itens_temp.append(Paragraph("", estilo_item))  # Completa a linha
            data_tec.append(itens_temp)

        if data_tec:
            t2 = Table(data_tec, colWidths=[9 * cm, 9 * cm])
            t2.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, cor_borda),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elementos.append(t2)
        else:
            elementos.append(Paragraph("Nenhuma especificação técnica detalhada.", estilo_item))

    except Exception as e:
        elementos.append(Paragraph(f"Aviso: Informações técnicas em formato simplificado.", estilo_item))

    doc.build(elementos)
    return buffer.getvalue()


# --- BLOCO DE LOGIN COM LIBERDADE TOTAL ---
if not st.session_state.auth:
    st.title("🏭 Acesso - Santa Cruz Produção")

    u = st.text_input("Seu Nome / Usuário").strip()
    # Trocamos o selectbox por text_input para você digitar o que quiser
    s_login = st.text_input("Setor / Cargo / Cliente (Ex: Laser, Visitante, PCP)").strip()
    p = st.text_input("Senha de Acesso", type="password")

    if st.button("Entrar", use_container_width=True):
        # 1. Login Mestre (Sempre funciona)
        if u == "admsantacruz" and p == "sc2024":
            st.session_state.update({
                "auth": True, "nivel": "ADM",
                "user_logado": "Administrador", "cargo_logado": "ADM"
            })
            st.rerun()

        # 2. Login com Autonomia Total (Aceita qualquer nome e setor)
        elif u != "" and s_login != "" and p == "123":
            # Se você digitar "ADM" ou "PCP" no setor, ele te dá nível ADM automaticamente
            nivel_acesso = "ADM" if s_login.upper() in ["ADM", "PCP"] else "USER"

            st.session_state.update({
                "auth": True,
                "user_logado": u,
                "cargo_logado": s_login,  # Salva exatamente o que você digitou
                "nivel": nivel_acesso
            })
            st.rerun()
        else:
            st.error("Preencha Nome e Setor. (Senha padrão: 123)")

    st.stop()

# --- MENU LATERAL (SIDEBAR) ---
with st.sidebar:
    # Centralização do ícone e título
    st.image("https://cdn-icons-png.flaticon.com/512/2206/2206368.png", width=100)
    st.title("Santa Cruz Nav")

    # Define as opções com base no nível de acesso definido no login
    opcoes = ["📋 Lista de OPs"]

    if st.session_state.nivel == "ADM":
        opcoes = ["📊 Relatório", "📋 Lista de OPs", "➕ Nova OP", "⚙️ Configurações"]
    elif st.session_state.nivel == "LIDER":
        opcoes = ["📋 Lista de OPs", "📊 Relatório"]

    # Seleção de Menu
    menu = st.radio("Selecione a página:", opcoes)

    st.divider()

    # Informações do Usuário com ícones para facilitar leitura rápida
    st.markdown(f"👤 **Usuário:** {st.session_state.user_logado}")
    st.markdown(f"🛠️ **Cargo:** {st.session_state.cargo_logado}")

    # Botão de Logoff com confirmação visual
    if st.button("🚪 Sair / Logoff", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- PÁGINA DE CONFIGURAÇÕES COMPLETA ---
if menu == "⚙️ Configurações":
    # Trava de Segurança: Apenas nível ADM acessa
    if st.session_state.nivel != "ADM":
        st.error("🚫 Acesso restrito ao Administrador.")
        st.stop()

    st.header("⚙️ Configurações do Sistema")
    t1, t2, t3 = st.tabs(["🏗️ Máquinas", "👷 Líderes", "🔑 Usuários"])

    # --- ABA 1: MÁQUINAS ---
    with t1:
        st.subheader("Gerenciar Máquinas e Checklists")
        val_n, val_c = "", ""

        # Recupera dados se houver uma edição pendente
        if st.session_state.edit_maq_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT nome, conjuntos FROM maquinas WHERE id=?",
                                   (st.session_state.edit_maq_id,)).fetchone()
                if res: val_n, val_c = res[0], res[1]

        with st.form("fm_maq"):
            n = st.text_input("Nome da Máquina", value=val_n, placeholder="Ex: Envasadora Linear")
            c = st.text_area("Checklist / Conjuntos (Separe por vírgula)", value=val_c,
                             help="Ex: Bicos, Esteira, Painel")
            c_m1, c_m2 = st.columns(2)

            if c_m1.form_submit_button("💾 SALVAR MÁQUINA"):
                if n:
                    with sqlite3.connect('fabrica_master.db') as conn:
                        if st.session_state.edit_maq_id:
                            conn.execute("UPDATE maquinas SET nome=?, conjuntos=? WHERE id=?",
                                         (n.upper(), c, st.session_state.edit_maq_id))
                        else:
                            conn.execute("INSERT OR REPLACE INTO maquinas (nome, conjuntos) VALUES (?,?)",
                                         (n.upper(), c))
                    st.session_state.edit_maq_id = None
                    st.success("Máquina salva!")
                    st.rerun()
                else:
                    st.error("Nome da máquina é obrigatório.")

            if c_m2.form_submit_button("➕ NOVO / CANCELAR"):
                st.session_state.edit_maq_id = None
                st.rerun()

        st.divider()
        # Listagem de Máquinas
        with sqlite3.connect('fabrica_master.db') as conn:
            m_df = pd.read_sql_query("SELECT * FROM maquinas", conn)

        for _, m in m_df.iterrows():
            with st.container(border=True):
                col_m1, col_m2, col_m3 = st.columns([4, 1, 1])
                col_m1.write(f"**{m['nome']}**")
                if col_m2.button("✏️", key=f"ed_m_{m['id']}"):
                    st.session_state.edit_maq_id = m['id']
                    st.rerun()
                if col_m3.button("🗑️", key=f"de_m_{m['id']}"):
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("DELETE FROM maquinas WHERE id=?", (m['id'],))
                    st.rerun()

    # --- ABA 2: LÍDERES ---
    with t2:
        st.subheader("Gerenciar Líderes de Setor")
        with sqlite3.connect('fabrica_master.db') as conn:
            s_df = pd.read_sql_query("SELECT * FROM setores", conn)

        val_nl = ""
        if st.session_state.edit_lid_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT nome FROM setores WHERE id=?", (st.session_state.edit_lid_id,)).fetchone()
                if res: val_nl = res[0]

        with st.form("f_lid"):
            c_l1, c_l2 = st.columns(2)
            nl = c_l1.text_input("Nome do Líder", value=val_nl)
            cl = c_l2.text_input("Cargo", value="LIDER")
            pl = st.text_input("Senha (apenas para novos ou alteração)", type="password")

            if st.form_submit_button("💾 SALVAR LÍDER"):
                if nl:
                    with sqlite3.connect('fabrica_master.db') as conn:
                        if st.session_state.edit_lid_id:
                            conn.execute("UPDATE setores SET nome=? WHERE id=?",
                                         (nl.upper(), st.session_state.edit_lid_id))
                        else:
                            conn.execute("INSERT OR IGNORE INTO setores (nome) VALUES (?)", (nl.upper(),))
                            if pl:  # Cria usuário correspondente
                                conn.execute("INSERT INTO usuarios (usuario, senha, cargo, ativo) VALUES (?,?,?,1)",
                                             (nl, pl, cl.upper()))
                    st.session_state.edit_lid_id = None
                    st.rerun()
                else:
                    st.error("Nome é obrigatório.")

        for _, s in s_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.write(f"👷 {s['nome']}")
                if c2.button("✏️", key=f"ed_s_{s['id']}"):
                    st.session_state.edit_lid_id = s['id']
                    st.rerun()
                if c3.button("🗑️", key=f"ds_{s['id']}"):
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("DELETE FROM setores WHERE id=?", (s['id'],))
                    st.rerun()

    # --- ABA 3: USUÁRIOS ---
    with t3:
        st.subheader("Controle de Acessos")
        val_u, val_c = "", ""
        if st.session_state.edit_usr_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT usuario, cargo FROM usuarios WHERE id=?",
                                   (st.session_state.edit_usr_id,)).fetchone()
                if res: val_u, val_c = res[0], res[1]

        with st.form("form_usuarios_geral"):
            u_nome = st.text_input("Usuário", value=val_u)
            u_senha = st.text_input("Senha", type="password",
                                    help="Deixe em branco para manter a atual (em caso de edição)")
            u_cargo = st.selectbox("Cargo", ["ADM", "PCP", "LIDER", "VENDEDOR"],
                                   index=0 if not val_c else ["ADM", "PCP", "LIDER", "VENDEDOR"].index(
                                       val_c.upper()) if val_c.upper() in ["ADM", "PCP", "LIDER", "VENDEDOR"] else 0)

            c_u1, c_u2 = st.columns(2)
            if c_u1.form_submit_button("💾 SALVAR USUÁRIO"):
                if u_nome:
                    with sqlite3.connect('fabrica_master.db') as conn:
                        if st.session_state.edit_usr_id:
                            if u_senha:
                                conn.execute("UPDATE usuarios SET usuario=?, senha=?, cargo=? WHERE id=?",
                                             (u_nome, u_senha, u_cargo.upper(), st.session_state.edit_usr_id))
                            else:
                                conn.execute("UPDATE usuarios SET usuario=?, cargo=? WHERE id=?",
                                             (u_nome, u_cargo.upper(), st.session_state.edit_usr_id))
                        else:
                            conn.execute("INSERT INTO usuarios (usuario, senha, cargo, ativo) VALUES (?,?,?,1)",
                                         (u_nome, u_senha, u_cargo.upper()))
                    st.session_state.edit_usr_id = None
                    st.rerun()
                else:
                    st.error("Usuário precisa de um nome.")

            if c_u2.form_submit_button("➕ NOVO"):
                st.session_state.edit_usr_id = None
                st.rerun()

        st.divider()
        with sqlite3.connect('fabrica_master.db') as conn:
            u_df = pd.read_sql_query("SELECT id, usuario, cargo, ativo FROM usuarios", conn)

        for _, u in u_df.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                stt = "🟢 Ativo" if u['ativo'] == 1 else "🔴 Inativo"
                col1.write(f"**{u['usuario']}** ({u['cargo']})")
                col2.write(stt)

                if col3.button("✏️", key=f"ed_u_{u['id']}"):
                    st.session_state.edit_usr_id = u['id']
                    st.rerun()

                # Impede a exclusão do administrador mestre
                if u['usuario'] != "admsantacruz":
                    if col4.button("🗑️", key=f"du_{u['id']}"):
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("DELETE FROM usuarios WHERE id=?", (u['id'],))
                        st.rerun()

# --- Nova Op ---
elif menu == "➕ Nova OP":
    st.header("➕ Gerenciar Ordem de Produção (Nuvem)")

    # 1. CONEXÃO E CARREGAMENTO
    try:
        # Mesma coisa aqui: leitura limpa da primeira aba
        df_base = conn_sheets.read(ttl=0)
    except Exception as e:
        st.error(f"Erro ao acessar a planilha: {e}")
        st.stop()

    edit_mode = st.session_state.edit_op_id is not None

    # Se estiver em modo edição, captura os dados da OP selecionada para preencher o formulário
    dados_op = {}
    if edit_mode:
        linha_selecionada = df_base[df_base['numero_op'] == st.session_state.edit_op_id]
        if not linha_selecionada.empty:
            dados_op = linha_selecionada.iloc[0].to_dict()

    # --- PASSO 1: DEFINIÇÃO DE ESTRUTURA (Campos Dinâmicos) ---
    if not st.session_state.layout_confirmado:
        st.subheader("Passo 1: Definir Especificações da Máquina")

        # Inicializa nomes das especificações se estiverem vazios
        if 'nomes_specs' not in st.session_state or not st.session_state.nomes_specs:
            st.session_state.nomes_specs = ["Alimentação", "Frasco", "Amostra", "Bicos", "Produto", "Estrutura"]

        # Interface para gerir os campos técnicos dinamicamente
        for i, nome in enumerate(st.session_state.nomes_specs):
            c_ed1, c_ed2 = st.columns([5, 1])
            st.session_state.nomes_specs[i] = c_ed1.text_input(f"Campo Técnico {i + 1}", value=nome,
                                                               key=f"spec_key_{i}")
            if c_ed2.button("🗑️", key=f"del_key_{i}"):
                st.session_state.nomes_specs.pop(i)
                st.rerun()

        if st.button("➕ Adicionar Nova Especificação"):
            st.session_state.nomes_specs.append("Novo Campo")
            st.rerun()

        st.divider()

        # Busca máquinas cadastradas no banco local SQLite para o selectbox
        with sqlite3.connect('fabrica_master.db') as db:
            maquinas_banco = [m[0] for m in db.execute("SELECT nome FROM maquinas").fetchall()]

        if not maquinas_banco:
            maquinas_banco = ["Envasadora", "Rotuladora", "Tampadora", "Linha Completa"]

        st.session_state.maq_atual = st.selectbox("Equipamento Base:", maquinas_banco)

        if st.button("Ir para Preenchimento de Dados ➡️"):
            st.session_state.layout_confirmado = True
            st.rerun()

    # --- PASSO 2: FORMULÁRIO DE DADOS ---
    else:
        st.subheader(f"Passo 2: Ficha Técnica - {st.session_state.maq_atual}")

        with st.form("form_sheets_op"):
            st.markdown("### 📄 Dados da Ordem de Produção")
            c1, c2, c3 = st.columns(3)
            f_op = c1.text_input("N° OP", value=dados_op.get("numero_op", ""))
            f_cli = c2.text_input("Cliente", value=dados_op.get("cliente", ""))

            # Tratamento robusto para campos de data vindos da planilha
            try:
                data_op_val = datetime.strptime(str(dados_op.get("data_op")),
                                                '%Y-%m-%d').date() if edit_mode else date.today()
            except:
                data_op_val = date.today()
            f_data_op = c3.date_input("Data da OP", value=data_op_val)

            c4, c5 = st.columns(2)
            try:
                d_ent = datetime.strptime(str(dados_op.get("data_entrega")),
                                          '%Y-%m-%d').date() if edit_mode else date.today()
            except:
                d_ent = date.today()
            f_entrega = c4.date_input("Data de Entrega", value=d_ent)
            f_vend_op = c5.text_input("Vendedor (OP)", value=dados_op.get("vendedor", ""))

            st.markdown("### 🛠️ Especificações Técnicas")
            g_specs = st.columns(3)
            specs_finais = {}

            # Carrega as especificações técnicas dinâmicas armazenadas em JSON
            try:
                raw_info = dados_op.get("info_adicionais_ficha", "{}")
                valores_specs = json.loads(raw_info) if isinstance(raw_info, str) else {}
            except:
                valores_specs = {}

            for i, nome in enumerate(st.session_state.nomes_specs):
                v_pre = valores_specs.get(nome, "")
                specs_finais[nome] = g_specs[i % 3].text_input(nome, value=v_pre)

            st.markdown("### 🚛 Logística e Fábrica")
            e1, e2, e3 = st.columns(3)
            f_mat = e1.text_input("Material Esteira", value=dados_op.get("est_material", ""))

            # Busca líderes cadastrados no banco local para o selectbox
            with sqlite3.connect('fabrica_master.db') as db:
                lideres_banco = [s[0] for s in db.execute("SELECT nome FROM setores").fetchall()]
            if not lideres_banco:
                lideres_banco = ["Líder Montagem", "Líder Usinagem", "Líder Elétrica"]

            f_lider = e2.selectbox("Líder Responsável", lideres_banco)
            f_cnpj = e3.text_input("CNPJ", value=dados_op.get("cnpj", ""))

            f_info = st.text_area("Informações Adicionais / Obs", value=dados_op.get("ast_instalacao", ""))

            # BOTÃO SALVAR (Ajustado para o nome da aba padronizado)
            btn_label = "💾 ATUALIZAR NA PLANILHA" if edit_mode else "🚀 SALVAR NA PLANILHA"
            submit = st.form_submit_button(btn_label)

            if submit:
                if not f_op:
                    st.error("O número da OP é obrigatório!")
                else:
                    nova_linha = {
                        "numero_op": f_op, "cliente": f_cli, "data_op": str(f_data_op),
                        "data_entrega": str(f_entrega), "vendedor": f_vend_op, "cnpj": f_cnpj,
                        "equipamento": st.session_state.maq_atual,
                        "ast_instalacao": f_info, "responsavel_setor": f_lider,
                        "info_adicionais_ficha": json.dumps(specs_finais),
                        "status": dados_op.get("status", "Em Produção"),
                        "progresso": dados_op.get("progresso", 0),
                        "acompanhamento_log": dados_op.get("acompanhamento_log", "[]"),
                        "est_material": f_mat
                    }

                    # Sincronização com o Google Sheets
                    df_final = df_base.copy()
                    if edit_mode:
                        # Se for edição, remove a entrada antiga antes de adicionar a nova
                        df_final = df_final[df_final['numero_op'] != st.session_state.edit_op_id]

                    df_final = pd.concat([df_final, pd.DataFrame([nova_linha])], ignore_index=True)

                    # Envio dos dados para a aba padronizada NOME_ABA ("DADOS")
                    conn_sheets.update(worksheet=NOME_ABA, data=df_final)

                    # Reset de estados após o sucesso
                    st.session_state.edit_op_id = None
                    st.session_state.layout_confirmado = False
                    st.success("✅ Dados sincronizados com o Google Sheets!")
                    st.rerun()

        if st.button("⬅️ Cancelar e Voltar"):
            st.session_state.edit_op_id = None
            st.session_state.layout_confirmado = False
            st.rerun()

# --- CONFIGURAÇÃO INICIAL E MANUTENÇÃO DO BANCO ---
# Garante a existência do diretório para uploads de anexos
if not os.path.exists("anexos"):
    os.makedirs("anexos")

# Manutenção do Banco Local: Garante que a coluna de anexos exista na tabela ordens
with sqlite3.connect('fabrica_master.db') as db_init:
    try:
        # Tenta adicionar a coluna; caso já exista, o erro é ignorado pelo 'except'
        db_init.execute("ALTER TABLE ordens ADD COLUMN anexo TEXT")
        db_init.commit()
    except Exception:
        # A coluna já existe ou o banco ainda não foi criado (iniciar_banco resolverá)
        pass


# --- LISTA DE OPs COMPLETA ---
if menu == "📋 Lista de OPs":
    st.header("📋 Controle de Ordens de Produção")

    # 1. LEITURA DOS DADOS (GOOGLE SHEETS)
    try:
        # Removemos o worksheet=NOME_ABA para evitar o Erro 400
        df = conn_sheets.read(ttl=0)
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        st.stop()


    if df.empty or "numero_op" not in df.columns:
        st.info("Nenhuma OP encontrada na nuvem. Vá em 'Nova OP' para cadastrar.")
    else:
        # Busca cargos ativos para o sistema de mensagens (Banco Local SQLite)
        with sqlite3.connect('fabrica_master.db') as db_local:
            res_cargos = db_local.execute("SELECT DISTINCT cargo FROM usuarios WHERE ativo=1").fetchall()
            cargos_chat = [c[0] for c in res_cargos]

        # Ordenação: Mais recentes no topo (extraindo números para ordenar corretamente)
        df['sort_num'] = df['numero_op'].astype(str).str.extract('(\d+)').fillna(0).astype(float)
        df = df.sort_values(by='sort_num', ascending=False)

        for _, op in df.iterrows():
            # Lógica de Alerta Visual (Cores baseadas na data de entrega)
            hoje = date.today()
            cor_alerta = "⚪"
            try:
                entrega = pd.to_datetime(op['data_entrega']).date()
                dias = (entrega - hoje).days
                if dias > 30:
                    cor_alerta = "🟢"
                elif 15 <= dias <= 30:
                    cor_alerta = "🟡"
                else:
                    cor_alerta = "🔴"
            except:
                dias = "N/A"

            # Card Expansível para cada Ordem de Produção
            titulo_card = f"{cor_alerta} OP {op['numero_op']} - {op['cliente']} | Entrega: {op['data_entrega']}"
            with st.expander(titulo_card):
                t1, t2, t3 = st.tabs(["📄 Ficha Técnica", "✅ Checklist", "💬 Acompanhamento"])

                with t1:
                    if cor_alerta == "🔴":
                        st.error(f"🚨 **URGENTE:** Entrega em {dias} dias!")

                    st.subheader("Dados do Projeto")
                    c_a, c_b, c_c = st.columns(3)
                    c_a.write(f"**Nº OP:** {op['numero_op']}")
                    c_a.write(f"**Cliente:** {op['cliente']}")
                    c_b.write(f"**Equipamento:** {op['equipamento']}")
                    c_b.write(f"**CNPJ:** {op['cnpj']}")
                    c_c.write(f"**Entrega:** {op['data_entrega']}")
                    c_c.write(f"**Líder:** {op.get('responsavel_setor', 'N/A')}")

                    st.divider()
                    st.subheader("🛠️ Especificações Técnicas")
                    try:
                        specs = json.loads(op['info_adicionais_ficha'])
                        cols_s = st.columns(3)
                        for i, (k, v) in enumerate(specs.items()):
                            cols_s[i % 3].write(f"**{k}:** {v}")
                    except:
                        st.write("Sem detalhes técnicos registrados.")

                    st.info(f"**Observações:** {op.get('ast_instalacao', '-')}")

                    # Botões de Ação
                    st.divider()
                    col_edit, col_pdf, col_del = st.columns(3)

                    if col_edit.button("✏️ Editar", key=f"btn_ed_{op['numero_op']}", use_container_width=True):
                        st.session_state.edit_op_id = op['numero_op']
                        st.session_state.layout_confirmado = True
                        st.rerun()

                    pdf_op = gerar_pdf_op(op)
                    col_pdf.download_button("📂 Baixar PDF", pdf_op, f"OP_{op['numero_op']}.pdf",
                                            key=f"pdf_{op['numero_op']}", use_container_width=True)

                    if st.session_state.nivel == "ADM":
                        if col_del.button("🗑️ Excluir", key=f"btn_del_{op['numero_op']}", use_container_width=True):
                            df_new = df[df['numero_op'] != op['numero_op']]
                            conn_sheets.update(worksheet=NOME_ABA, data=df_new)
                            st.success("OP removida!")
                            st.rerun()

                with t2:
                    st.write("### Progresso da Produção")
                    with sqlite3.connect('fabrica_master.db') as db_local:
                        m_info = db_local.execute("SELECT conjuntos FROM maquinas WHERE nome=?",
                                                  (op['equipamento'],)).fetchone()

                    itens_checklist = [i.strip() for i in m_info[0].split(",")] if m_info and m_info[0] else []
                    concluidos = str(op.get('checks_concluidos', '')).split("|") if op.get('checks_concluidos') else []

                    if itens_checklist:
                        selecionados = [i for i in itens_checklist if
                                        st.checkbox(i, i in concluidos, key=f"ck_{op['numero_op']}_{i}")]
                        if st.button("💾 Atualizar Progresso", key=f"sck_{op['numero_op']}"):
                            percentual = int((len(selecionados) / len(itens_checklist)) * 100)
                            status_txt = "Concluído" if percentual == 100 else "Em Produção"

                            df.loc[df['numero_op'] == op['numero_op'], 'progresso'] = percentual
                            df.loc[df['numero_op'] == op['numero_op'], 'checks_concluidos'] = "|".join(selecionados)
                            df.loc[df['numero_op'] == op['numero_op'], 'status'] = status_txt

                            conn_sheets.update(worksheet=NOME_ABA, data=df)
                            st.success(f"Progresso de {percentual}% salvo!")
                            st.rerun()

                with t3:
                    import pytz

                    fuso_br = pytz.timezone('America/Sao_Paulo')
                    agora = datetime.now(fuso_br).strftime("%d/%m %H:%M")
                    try:
                        logs = json.loads(op.get('acompanhamento_log', '[]'))
                    except:
                        logs = []

                    with st.form(f"chat_{op['numero_op']}"):
                        dest = st.selectbox("Enviar para:", cargos_chat)
                        mensagem = st.text_area("Sua mensagem")
                        if st.form_submit_button("Enviar"):
                            if mensagem:
                                logs.append({"user": st.session_state.user_logado, "destino": dest, "data": agora,
                                             "msg": mensagem})
                                df.loc[df['numero_op'] == op['numero_op'], 'acompanhamento_log'] = json.dumps(logs)
                                conn_sheets.update(worksheet=NOME_ABA, data=df)
                                st.rerun()

                    for m in reversed(logs):
                        st.chat_message("user").write(
                            f"**{m['user']}** → **{m['destino']}** ({m['data']})\n\n{m['msg']}")

# --- RELATÓRIO DINÂMICO ---
elif menu == "📊 Relatório":
    st.header("📊 Painel de Controle de Produção")

    # 1. LEITURA DOS DADOS (GOOGLE SHEETS)
    try:
        df_rel = conn_sheets.read(ttl=0)
    except Exception as e:
        st.error(f"Erro: {e}")
        st.stop()

    if not df_rel.empty:
        # 2. TRATAMENTO DE DADOS PARA GRÁFICOS
        # Converte progresso para numérico; 'coerce' transforma erros em NaN, que depois viram 0
        df_rel['progresso'] = pd.to_numeric(df_rel['progresso'], errors='coerce').fillna(0)

        # Garante que as colunas categóricas não tenham valores nulos para o Plotly
        df_rel['responsavel_setor'] = df_rel['responsavel_setor'].fillna("Não Definido")
        df_rel['equipamento'] = df_rel['equipamento'].fillna("Não Informado")

        # Filtramos apenas o que ainda está em linha de produção (Progresso < 100)
        df_fluxo = df_rel[df_rel['progresso'] < 100].copy()

        if df_fluxo.empty:
            st.success("🎉 Todas as OPs foram concluídas! Não há carga pendente no momento.")
            # Opção de visualizar o histórico completo mesmo sem pendências
            if st.checkbox("Visualizar histórico de OPs concluídas"):
                df_fluxo = df_rel.copy()

        if not df_fluxo.empty:
            # 3. MÉTRICAS RÁPIDAS
            c1, c2, c3 = st.columns(3)
            c1.metric("OPs em Aberto", len(df_fluxo))
            c2.metric("Líderes com Carga", df_fluxo['responsavel_setor'].nunique())

            prog_medio = df_fluxo['progresso'].mean()
            c3.metric("Progresso Médio", f"{prog_medio:.1f}%")

            st.divider()

            # 4. EXPORTAÇÃO (PDF DO MAPA GERAL)
            # Mapeamento para nomes amigáveis no PDF
            df_pdf = df_fluxo.rename(columns={
                'numero_op': 'Nº OP',
                'cliente': 'Cliente',
                'equipamento': 'Máquina',
                'responsavel_setor': 'Líder',
                'data_entrega': 'Entrega',
                'progresso': 'Progresso %'
            })

            # Gera o PDF usando a função revisada no Trecho 2
            pdf_geral = gerar_pdf_relatorio_geral(df_pdf)
            st.download_button(
                label="📥 Baixar Mapa Geral de Produção (PDF)",
                data=pdf_geral,
                file_name=f"MAPA_SANTA_CRUZ_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

            # 5. GRÁFICOS DINÂMICOS
            col_esq, col_dir = st.columns(2)

            with col_esq:
                st.subheader("👥 Carga por Líder")
                # Gráfico de Rosca para distribuição de trabalho
                fig_pizza = px.pie(
                    df_fluxo,
                    names='responsavel_setor',
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    title="Distribuição de OPs por Líder"
                )
                st.plotly_chart(fig_pizza, use_container_width=True)

            with col_dir:
                st.subheader("📈 Progresso Individual")
                # Gráfico de Barras para acompanhamento de status
                fig_bar = px.bar(
                    df_fluxo,
                    x='numero_op',
                    y='progresso',
                    color='responsavel_setor',
                    text='progresso',
                    title="Acompanhamento % por Ordem",
                    labels={'numero_op': 'Nº da Ordem', 'progresso': 'Progresso (%)'}
                )
                fig_bar.update_traces(texttemplate='%{text}%', textposition='outside')
                st.plotly_chart(fig_bar, use_container_width=True)

            st.divider()

            # 6. TABELA DETALHADA (DATAFRAME INTERATIVO)
            st.subheader("📋 Detalhamento da Produção")
            colunas_exibicao = ['numero_op', 'cliente', 'equipamento', 'responsavel_setor', 'data_entrega', 'progresso']
            st.dataframe(
                df_fluxo[colunas_exibicao],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("A planilha está vazia ou a aba 'DADOS' não foi populada. Cadastre uma OP para gerar o relatório.")












