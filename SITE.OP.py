import streamlit as st
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime, date
from io import BytesIO
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether



# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Santa Cruz Produção Master", layout="wide")
if not os.path.exists("anexos"): os.makedirs("anexos")

# --- ESTADO DE SESSÃO (MEMÓRIA DO APP) ---
if 'auth' not in st.session_state: st.session_state.auth = False
if 'user_logado' not in st.session_state: st.session_state.user_logado = ""
if 'cargo_logado' not in st.session_state: st.session_state.cargo_logado = ""
if 'nivel' not in st.session_state: st.session_state.nivel = ""
if 'layout_confirmado' not in st.session_state: st.session_state.layout_confirmado = False
if 'maq_atual' not in st.session_state: st.session_state.maq_atual = ""
if 'campos_dinamicos' not in st.session_state:
    st.session_state.campos_dinamicos = {"Alimentação": "", "Produto": "", "Estrutura": "", "Frascos": "",
                                         "Produção": "", "Bicos": ""}
if 'edit_op_id' not in st.session_state: st.session_state.edit_op_id = None
if 'edit_lid_id' not in st.session_state: st.session_state.edit_lid_id = None
if 'edit_usr_id' not in st.session_state: st.session_state.edit_usr_id = None
if 'edit_maq_id' not in st.session_state: st.session_state.edit_maq_id = None


def iniciar_banco():
    with sqlite3.connect('fabrica_master.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS ordens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, numero_op TEXT, equipamento TEXT, cliente TEXT, cnpj TEXT, 
                        data_op TEXT, vendedor TEXT, data_entrega TEXT, responsavel_setor TEXT, 
                        est_material TEXT, est_comprimento TEXT, est_altura TEXT, est_largura TEXT, est_plataforma TEXT,
                        dist_vendedor TEXT, dist_revisor TEXT, dist_pcp TEXT, dist_projeto TEXT, dist_eletrica TEXT, dist_montagem TEXT,
                        exp_endereco TEXT, ast_instalacao TEXT, info_adicionais_ficha TEXT DEFAULT "{}",
                        progresso INTEGER DEFAULT 0, checks_concluidos TEXT DEFAULT "", status TEXT DEFAULT 'Em Produção',
                        acompanhamento_log TEXT DEFAULT "[]")''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS modelos_op (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_maquina TEXT UNIQUE, layout_json TEXT)''')
        c.execute(
            "CREATE TABLE IF NOT EXISTS maquinas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, conjuntos TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS setores (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, senha TEXT, cargo TEXT, ativo INTEGER)")
        conn.commit()


iniciar_banco()

# --- FUNÇÃO PDF PROFISSIONAL (REVISADA E CORRIGIDA) ---
def gerar_pdf_relatorio_geral(df_relatorio):
    buffer = BytesIO()
    # Configuração da Folha A4 em pé
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

    # Estilo para o texto dentro das células (evita invasão de coluna)
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
    responsavel = st.session_state.user_logado
    titulo = Paragraph("<b>MAPA GERAL DE PRODUÇÃO - SANTA CRUZ</b>", styles['Title'])
    sub_titulo = Paragraph(f"Responsável: {responsavel} | Data: {datetime.now().strftime('%d/%m/%Y')}",
                           estilo_responsavel)

    elementos.append(titulo)
    elementos.append(sub_titulo)
    elementos.append(Spacer(1, 0.5 * cm))

    # --- MONTAGEM DA TABELA ---
    # Usamos Paragraph no cabeçalho também para manter o padrão
    dados_tabela = [[
        Paragraph("<b>Nº OP</b>", estilo_celula),
        Paragraph("<b>Cliente</b>", estilo_celula),
        Paragraph("<b>Máquina</b>", estilo_celula),
        Paragraph("<b>Líder</b>", estilo_celula),
        Paragraph("<b>Entrega</b>", estilo_celula),
        Paragraph("<b>Status</b>", estilo_celula)
    ]]

    # Conteúdo vindo do DataFrame
    for _, linha in df_relatorio.iterrows():
        dados_tabela.append([
            Paragraph(str(linha['Nº OP']), estilo_celula),
            Paragraph(str(linha['Cliente']), estilo_celula),
            Paragraph(str(linha['Máquina']), estilo_celula),
            Paragraph(str(linha['Líder']), estilo_celula),
            Paragraph(str(linha['Entrega']), estilo_celula),
            Paragraph(f"{linha['Progresso %']}%", estilo_celula)
        ])

    # Estilo Visual da Tabela
    estilo_tab = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A242F")),  # Fundo azul marinho
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    # Distribuição das Larguras (Total 19cm)
    # OP(2.2) + Cliente(5.8) + Máquina(4.0) + Líder(3.5) + Entrega(2.0) + Status(1.5)
    t = Table(dados_tabela, colWidths=[2.2 * cm, 5.8 * cm, 4.0 * cm, 3.5 * cm, 2.0 * cm, 1.5 * cm])
    t.setStyle(estilo_tab)
    elementos.append(t)

    # Rodapé simples
    elementos.append(Spacer(1, 1 * cm))
    elementos.append(
        Paragraph(f"<center><font size=8>Relatório gerado automaticamente pelo Sistema Santa Cruz</font></center>",
                  styles['Normal']))

    doc.build(elementos)
    return buffer.getvalue()


def gerar_pdf_op(op_raw):
    op = dict(op_raw)
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

    # Subtítulo: Líder Responsável (Identificação de quem a OP pertence)
    # Pegamos o valor e garantimos que, se for None, vire uma string vazia ""
    lider_val = op.get('responsavel_setor') or "NÃO DEFINIDO"
    # Agora transformamos em maiúsculo sem risco de erro
    elementos.append(Paragraph(f"Líder Responsável: <b>{str(lider_val).upper()}</b>", estilo_sub_lider))

    elementos.append(Spacer(1, 0.5 * cm))

    # --- TABELA DE DADOS DO PROJETO ---
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
        specs = json.loads(op.get('info_adicionais_ficha', '{}'))
        data_tec = []
        itens_temp = []
        for k, v in specs.items():
            itens_temp.append(Paragraph(f"<b>{k}:</b> {v}", estilo_item))
            if len(itens_temp) == 2:
                data_tec.append(itens_temp)
                itens_temp = []
        if itens_temp:
            itens_temp.append("")
            data_tec.append(itens_temp)

        if data_tec:
            t2 = Table(data_tec, colWidths=[9 * cm, 9 * cm])
            t2.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, cor_borda), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            elementos.append(t2)
    except:
        elementos.append(Paragraph("Erro nas especificações.", estilo_item))

    doc.build(elementos)
    return buffer.getvalue()

# --- LOGIN ---
if not st.session_state.auth:
    st.title("🏭 Login - Santa Cruz Produção Master")
    with sqlite3.connect('fabrica_master.db') as conn:
        res_c = conn.execute("SELECT DISTINCT cargo FROM usuarios").fetchall()
        cargos = [c[0] for c in res_c]
    if "ADM" not in cargos: cargos.append("ADM")
    if "PCP" not in cargos: cargos.append("PCP")
    u = st.text_input("Usuário")
    s_login = st.selectbox("Cargo", cargos)
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admsantacruz" and p == "sc2024" and s_login == "ADM":
            st.session_state.update(
                {"auth": True, "nivel": "ADM", "user_logado": "Administrador", "cargo_logado": "ADM"})
            st.rerun()
        else:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT cargo, ativo, usuario FROM usuarios WHERE usuario=? AND senha=? AND cargo=?",
                                   (u, p, s_login)).fetchone()
            if res and res[1] == 1:
                st.session_state.update({"auth": True, "user_logado": res[2], "cargo_logado": res[0]})
                st.session_state.nivel = "ADM" if res[0] == "PCP" else (
                    "LIDER" if "LIDER" in res[0].upper() else "USER")
                st.rerun()
            else:
                st.error("Acesso negado.")
    st.stop()

# --- LOGICA DE NAVEGAÇÃO UNIFICADA (CORREÇÃO DO REDIRECIONAMENTO) ---
opcoes = ["📋 Lista de OPs", "📊 Relatório"]

# 1. Define quem vê o menu Nova OP
if st.session_state.nivel in ["ADM", "LIDER"]:
    opcoes.insert(1, "➕ Nova OP")

# 2. Define quem vê Configurações
if st.session_state.nivel == "ADM":
    opcoes.append("⚙️ Configurações")

# --- O SEGREDO ESTÁ AQUI ---
# Se o botão 'Editar' foi clicado, o edit_op_id não é mais None.
# Então, forçamos o menu a selecionar a "➕ Nova OP" (que está no index 1).
if st.session_state.edit_op_id is not None:
    menu_index = opcoes.index("➕ Nova OP")
else:
    menu_index = 0

# Cria o menu com o index dinâmico
menu = st.sidebar.radio("Navegação", opcoes, index=menu_index, key="menu_principal")


# --- PÁGINA DE CONFIGURAÇÕES COMPLETA
if menu == "⚙️ Configurações":
    # Trava de Segurança
    if st.session_state.nivel != "ADM":
        st.error("🚫 Acesso restrito ao Administrador.")
        st.stop()

    st.header("⚙️ Configurações do Sistema")
    t1, t2, t3 = st.tabs(["🏗️ Máquinas", "👷 Líderes", "🔑 Usuários"])

    # --- ABA 1: MÁQUINAS ---
    with t1:
        st.subheader("Gerenciar Máquinas e Checklists")
        val_n, val_c = "", ""
        if st.session_state.edit_maq_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT nome, conjuntos FROM maquinas WHERE id=?",
                                   (st.session_state.edit_maq_id,)).fetchone()
                if res: val_n, val_c = res[0], res[1]

        with st.form("fm_maq"):
            n = st.text_input("Nome da Máquina", value=val_n)
            c = st.text_area("Checklist / Conjuntos (Separe por vírgula)", value=val_c)
            c_m1, c_m2 = st.columns(2)
            if c_m1.form_submit_button("💾 SALVAR MÁQUINA"):
                with sqlite3.connect('fabrica_master.db') as conn:
                    if st.session_state.edit_maq_id:
                        conn.execute("UPDATE maquinas SET nome=?, conjuntos=? WHERE id=?",
                                     (n, c, st.session_state.edit_maq_id))
                    else:
                        conn.execute("INSERT OR REPLACE INTO maquinas (nome, conjuntos) VALUES (?,?)", (n, c))
                st.session_state.edit_maq_id = None
                st.rerun()
            if c_m2.form_submit_button("➕ NOVO"):
                st.session_state.edit_maq_id = None
                st.rerun()

        st.divider()
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
        st.subheader("Gerenciar Líderes e Acessos de Fábrica")
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
            pl = st.text_input("Senha de Acesso", type="password")

            if st.form_submit_button("💾 SALVAR LÍDER E CRIAR USUÁRIO"):
                if nl:
                    with sqlite3.connect('fabrica_master.db') as conn:
                        if st.session_state.edit_lid_id:
                            conn.execute("UPDATE setores SET nome=? WHERE id=?",
                                         (nl.upper(), st.session_state.edit_lid_id))
                        else:
                            conn.execute("INSERT OR IGNORE INTO setores (nome) VALUES (?)", (nl.upper(),))
                            if pl:  # Só cria usuário se houver senha
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
        st.subheader("Gerenciar Todos os Usuários")
        val_u, val_c = "", ""
        if st.session_state.edit_usr_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT usuario, cargo FROM usuarios WHERE id=?",
                                   (st.session_state.edit_usr_id,)).fetchone()
                if res: val_u, val_c = res[0], res[1]

        with st.form("form_usuarios_geral"):
            u_nome = st.text_input("Nome de Usuário", value=val_u)
            u_senha = st.text_input("Senha", type="password")
            u_cargo = st.text_input("Cargo (ADM, PCP, LIDER, VENDEDOR)", value=val_c)
            c_u1, c_u2 = st.columns(2)
            if c_u1.form_submit_button("💾 SALVAR ALTERAÇÕES"):
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
            if c_u2.form_submit_button("➕ NOVO"):
                st.session_state.edit_usr_id = None
                st.rerun()

        st.divider()
        with sqlite3.connect('fabrica_master.db') as conn:
            u_df = pd.read_sql_query("SELECT id, usuario, cargo, ativo FROM usuarios", conn)
        for _, u in u_df.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                stt = "🟢" if u['ativo'] == 1 else "🔴"
                col1.write(f"**{u['usuario']}** ({u['cargo']}) {stt}")
                if col2.button("🔄", key=f"tu_{u['id']}"):
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("UPDATE usuarios SET ativo=? WHERE id=?", (0 if u['ativo'] == 1 else 1, u['id']))
                    st.rerun()
                if col3.button("✏️", key=f"ed_u_{u['id']}"):
                    st.session_state.edit_usr_id = u['id']
                    st.rerun()
                if col4.button("🗑️", key=f"du_{u['id']}"):
                    if u['usuario'] != "admsantacruz":
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("DELETE FROM usuarios WHERE id=?", (u['id'],))
                        st.rerun()

# --- Nova Op ---
elif menu == "➕ Nova OP":
    st.header("➕ Gerenciar Ordem de Produção (Nuvem)")

    # 1. CONEXÃO E CARREGAMENTO
    # Conecta ao Sheets e lê a base atual para saber se é uma edição
    df_base = conn.read(worksheet="Página1", ttl=0)
    edit_mode = st.session_state.edit_op_id is not None

    # Se estiver em modo edição, tenta capturar os dados da OP selecionada
    dados_op = {}
    if edit_mode:
        # Filtra a linha correspondente ao número da OP
        linha_selecionada = df_base[df_base['numero_op'] == st.session_state.edit_op_id]
        if not linha_selecionada.empty:
            dados_op = linha_selecionada.iloc[0].to_dict()

    # --- PASSO 1: ESTRUTURA TÉCNICA ---
    if not st.session_state.layout_confirmado:
        st.subheader("Passo 1: Definir Especificações da Máquina")

        if 'nomes_specs' not in st.session_state:
            # Padrão solicitado
            st.session_state.nomes_specs = ["Alimentação", "Frasco", "Amostra", "Bicos", "Produto", "Estrutura"]

        # Interface para gerir os campos (Incluir/Excluir)
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
        # Seleção do Equipamento (Pode ser uma aba no Sheets também)
        maquinas_lista = ["Envasadora", "Rotuladora", "Tampadora", "Linha Completa"]
        st.session_state.maq_atual = st.selectbox("Equipamento Base:", maquinas_lista)

        if st.button("Ir para Preenchimento de Dados ➡️"):
            st.session_state.layout_confirmado = True
            st.rerun()

    # --- PASSO 2: FORMULÁRIO COMPLETO ---
    else:
        st.subheader(f"Passo 2: Ficha Técnica - {st.session_state.maq_atual}")

        with st.form("form_sheets_op"):
            # BLOCO: DADOS DA OP
            st.markdown("### 📄 Dados da Ordem de Produção")
            c1, c2, c3 = st.columns(3)
            f_op = c1.text_input("N° OP", value=dados_op.get("numero_op", ""))
            f_cli = c2.text_input("Cliente", value=dados_op.get("cliente", ""))
            f_data_op = c3.date_input("Data da OP", value=date.today())

            c4, c5 = st.columns(2)
            # Tenta converter a data salva ou usa hoje
            try:
                d_ent = datetime.strptime(dados_op.get("data_entrega"), '%Y-%m-%d').date()
            except:
                d_ent = date.today()
            f_entrega = c4.date_input("Data de Entrega", value=d_ent)
            f_vend_op = c5.text_input("Vendedor (OP)", value=dados_op.get("vendedor", ""))

            # BLOCO: DADOS DO CLIENTE
            st.markdown("### 👥 Dados do Cliente")
            cc1, cc2 = st.columns(2)
            f_cnpj = cc1.text_input("CNPJ", value=dados_op.get("cnpj", ""))
            f_end = cc2.text_input("Endereço Completo", value=dados_op.get("exp_endereco", ""))

            # BLOCO: ESPECIFICAÇÕES DINÂMICAS
            st.markdown("### 🛠️ Especificações da Máquina")
            g_specs = st.columns(3)
            specs_finais = {}
            # Se for edição, tenta carregar os valores salvos no JSON
            valores_specs = {}
            if edit_mode and dados_op.get("info_adicionais_ficha"):
                valores_specs = json.loads(dados_op.get("info_adicionais_ficha"))

            for i, nome in enumerate(st.session_state.nomes_specs):
                v_pre = valores_specs.get(nome, "")
                specs_finais[nome] = g_specs[i % 3].text_input(nome, value=v_pre)

            # BLOCO: DADOS DA ESTEIRA
            st.markdown("### 🚛 Dados da Esteira")
            e1, e2, e3, e4, e5 = st.columns(5)
            f_mat = e1.text_input("Material", value=dados_op.get("est_material", ""))
            f_alt = e2.text_input("Altura", value=dados_op.get("est_altura", ""))
            f_com = e3.text_input("Comprimento", value=dados_op.get("est_comprimento", ""))
            f_lar = e4.text_input("Largura", value=dados_op.get("est_largura", ""))
            f_pla = e5.text_input("Plataforma", value=dados_op.get("est_plataforma", ""))

            # BLOCO: DISTRIBUIÇÃO INTERNA
            st.markdown("### 🏢 Distribuição Interna")
            d1, d2, d3 = st.columns(3)
            f_dist_vend = d1.text_input("Vendedor (Distrib.)", value=dados_op.get("dist_vendedor", ""))
            f_revi = d2.text_input("Revisor", value=dados_op.get("dist_revisor", ""))
            f_pcp = d3.text_input("PCP", value=dados_op.get("dist_pcp", ""))

            d4, d5, d6 = st.columns(3)
            f_proj = d4.text_input("Projeto", value=dados_op.get("dist_projeto", ""))
            f_elet = d5.text_input("Elétrica", value=dados_op.get("dist_eletrica", ""))
            f_mont = d6.text_input("Montagem", value=dados_op.get("dist_montagem", ""))

            st.markdown("### 📝 Finalização")
            f_info = st.text_area("Informações Adicionais", value=dados_op.get("ast_instalacao", ""))
            f_lider = st.selectbox("Líder do Setor Responsável", ["Líder Montagem", "Líder Usinagem", "Líder Elétrica"])

            # BOTÃO DE SALVAMENTO NO GOOGLE SHEETS
            btn_label = "💾 ATUALIZAR NA PLANILHA" if edit_mode else "🚀 SALVAR NA PLANILHA"
            submit = st.form_submit_button(btn_label)

            if submit:
                # 1. Prepara a nova linha
                nova_linha = {
                    "numero_op": f_op, "cliente": f_cli, "data_op": str(f_data_op),
                    "data_entrega": str(f_entrega), "vendedor": f_vend_op, "cnpj": f_cnpj,
                    "exp_endereco": f_end, "equipamento": st.session_state.maq_atual,
                    "est_material": f_mat, "est_altura": f_alt, "est_comprimento": f_com,
                    "est_largura": f_lar, "est_plataforma": f_pla, "dist_vendedor": f_dist_vend,
                    "dist_revisor": f_revi, "dist_pcp": f_pcp, "dist_projeto": f_proj,
                    "dist_eletrica": f_elet, "dist_montagem": f_mont, "ast_instalacao": f_info,
                    "responsavel_setor": f_lider, "info_adicionais_ficha": json.dumps(specs_finais),
                    "status": dados_op.get("status", "Em Produção"),
                    "progresso": dados_op.get("progresso", 0)
                }

                # 2. Se for edição, removemos a linha antiga do DataFrame antes de adicionar a nova
                if edit_mode:
                    df_base = df_base[df_base['numero_op'] != st.session_state.edit_op_id]

                # 3. Adiciona a nova linha e envia para o Sheets
                df_atualizado = pd.concat([df_base, pd.DataFrame([nova_linha])], ignore_index=True)
                conn.update(worksheet="Página1", data=df_atualizado)

                # 4. Limpa estados e avisa o utilizador
                st.session_state.edit_op_id = None
                st.session_state.layout_confirmado = False
                st.success("✅ Dados sincronizados com o Google Sheets!")
                st.rerun()

        if st.button("⬅️ Cancelar e Voltar"):
            st.session_state.edit_op_id = None
            st.session_state.layout_confirmado = False
            st.rerun()

# --- CONFIGURAÇÃO INICIAL (Coloque isso no início do código, antes do menu) ---
if not os.path.exists("anexos"):
    os.makedirs("anexos")

with sqlite3.connect('fabrica_master.db') as conn:
    try:
        conn.execute("ALTER TABLE ordens ADD COLUMN anexo TEXT")
    except:
        pass

# --- LISTA DE OPs COMPLETA COM ANEXOS E CORES ---
# --- ABA: LISTA DE OPs ---
if menu == "📋 Lista de OPs":
    st.header("📋 Controle de Ordens de Produção")

    # 1. LEITURA DOS DADOS (GOOGLE SHEETS)
    try:
        df = conn.read(worksheet="Página1", ttl=0)
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        st.stop()

    if df.empty or "numero_op" not in df.columns:
        st.info("Nenhuma OP encontrada na planilha. Verifique os cabeçalhos.")
    else:
        # Busca cargos para o chat
        cargos_chat = ["ADM", "PCP", "LIDER", "MONTAGEM", "ELETRICA", "PROJETO"]

        # Ordenação Decrescente (Ex: SC-0512 no topo)
        df['sort_num'] = df['numero_op'].astype(str).str.extract('(\d+)').fillna(0).astype(float)
        df = df.sort_values(by='sort_num', ascending=False)

        for _, op in df.iterrows():
            # Lógica de Alerta por Data
            hoje = date.today()
            cor_alerta = "⚪"
            try:
                data_ent_str = str(op['data_entrega'])
                entrega = datetime.strptime(data_ent_str, '%Y-%m-%d').date()
                dias = (entrega - hoje).days
                if dias > 30:
                    cor_alerta = "🟢"
                elif 15 <= dias <= 30:
                    cor_alerta = "🟡"
                else:
                    cor_alerta = "🔴"
            except:
                pass

            with st.expander(f"{cor_alerta} OP {op['numero_op']} - {op['cliente']} | Entrega: {op['data_entrega']}"):
                t1, t2, t3 = st.tabs(["📄 Ficha Técnica", "✅ Checklist", "💬 Acompanhamento"])

                with t1:
                    st.subheader("Dados Gerais e Cliente")
                    c_a, c_b, c_c = st.columns(3)
                    c_a.write(f"**Nº OP:** {op.get('numero_op', 'N/A')}")
                    c_a.write(f"**Cliente:** {op.get('cliente', 'N/A')}")
                    c_b.write(f"**CNPJ:** {op.get('cnpj', 'N/A')}")
                    c_b.write(f"**Vendedor:** {op.get('vendedor', 'N/A')}")
                    c_c.write(f"**Emissão:** {op.get('data_op', 'N/A')}")
                    c_c.write(f"**Entrega:** {op.get('data_entrega', 'N/A')}")
                    st.write(f"📍 **Endereço:** {op.get('exp_endereco', 'N/A')}")

                    st.divider()
                    st.subheader("🛠️ Especificações da Máquina")
                    try:
                        specs = json.loads(op['info_adicionais_ficha'])
                        cols = st.columns(3)
                        for i, (k, v) in enumerate(specs.items()):
                            cols[i % 3].write(f"**{k}:** {v}")
                    except:
                        st.write("Sem especificações técnicas detalhadas.")

                    st.divider()
                    st.subheader("🚛 Dados da Esteira")
                    e1, e2, e3, e4, e5 = st.columns(5)
                    e1.write(f"**Material:**\n{op.get('est_material', '-')}")
                    e2.write(f"**Altura:**\n{op.get('est_altura', '-')}")
                    e3.write(f"**Comp.:**\n{op.get('est_comprimento', '-')}")
                    e4.write(f"**Largura:**\n{op.get('est_largura', '-')}")
                    e5.write(f"**Plat.:**\n{op.get('est_plataforma', '-')}")

                    st.divider()
                    st.subheader("🏢 Distribuição e Fábrica")
                    d1, d2, d3, d4 = st.columns(4)
                    d1.write(f"**PCP:** {op.get('dist_pcp', '-')}")
                    d2.write(f"**Projeto:** {op.get('dist_projeto', '-')}")
                    d3.write(f"**Elétrica:** {op.get('dist_eletrica', '-')}")
                    d4.write(f"**Montagem:** {op.get('dist_montagem', '-')}")

                    st.info(
                        f"**Líder Responsável:** {op.get('responsavel_setor', '-')}\n\n**Obs:** {op.get('ast_instalacao', '-')}")

                    # BOTÕES DE AÇÃO
                    st.divider()
                    col_edit, col_pdf, col_del = st.columns(3)

                    if col_edit.button("✏️ Editar", key=f"btn_ed_{op['numero_op']}", use_container_width=True):
                        st.session_state.edit_op_id = op['numero_op']
                        st.session_state.layout_confirmado = True
                        st.rerun()

                    # Chamada da função de PDF
                    col_pdf.download_button("📂 PDF", gerar_pdf_op(op), f"OP_{op['numero_op']}.pdf",
                                            key=f"pdf_{op['numero_op']}", use_container_width=True)

                    if st.session_state.nivel == "ADM":
                        if col_del.button("🗑️ Excluir", key=f"btn_del_{op['numero_op']}", use_container_width=True):
                            df_new = df[df['numero_op'] != op['numero_op']]
                            conn.update(worksheet="Página1", data=df_new)
                            st.rerun()

                with t2:
                    st.write("### Progresso da Produção")
                    prog = int(op.get('progresso', 0))
                    st.progress(prog / 100)
                    st.write(f"Status Atual: **{op.get('status', 'Em Produção')}**")

                with t3:
                    import pytz

                    fuso_br = pytz.timezone('America/Sao_Paulo')
                    agora_br = datetime.now(fuso_br).strftime("%d/%m %H:%M")

                    try:
                        logs = json.loads(op['acompanhamento_log']) if op['acompanhamento_log'] else []
                    except:
                        logs = []

                    with st.form(f"chat_{op['numero_op']}"):
                        dest = st.selectbox("Para:", cargos_chat)
                        msg = st.text_area("Sua mensagem")
                        if st.form_submit_button("Enviar Mensagem"):
                            if msg:
                                logs.append({"cargo_destino": dest, "user_origem": st.session_state.user_logado,
                                             "data": agora_br, "msg": msg})
                                df.loc[df['numero_op'] == op['numero_op'], 'acompanhamento_log'] = json.dumps(logs)
                                conn.update(worksheet="Página1", data=df)
                                st.rerun()

                    for m in reversed(logs):
                        st.chat_message(
                            "user" if m['user_origem'] == st.session_state.user_logado else "assistant").write(
                            f"**{m['user_origem']}** para **{m['cargo_destino']}** - 🕒 {m['data']}\n\n{m['msg']}")

# --- RELATÓRIO DINÂMICO COM GRÁFICO POR LÍDER ---
elif menu == "📊 Relatório":
    st.header("📊 Painel de Controle de Produção")

    # 1. LEITURA DOS DADOS (GOOGLE SHEETS)
    try:
        df_rel = conn.read(worksheet="Página1", ttl=0)
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        st.stop()

    if not df_rel.empty:
        # 2. FILTRAR DADOS PARA O RELATÓRIO (Apenas OPs em andamento)
        # Garantimos que a coluna progresso seja tratada como número
        df_rel['progresso'] = pd.to_numeric(df_rel['progresso'], errors='coerce').fillna(0)
        df_fluxo = df_rel[df_rel['progresso'] < 100].copy()

        if df_fluxo.empty:
            st.info("Todas as OPs cadastradas já foram concluídas (100%).")
        else:
            # 3. MÉTRICAS DE RESUMO
            c1, c2, c3 = st.columns(3)
            c1.metric("OPs em Produção", len(df_fluxo))
            c2.metric("Líderes Ativos",
                      df_fluxo['responsavel_setor'].nunique() if 'responsavel_setor' in df_fluxo.columns else 0)

            # 4. BOTÃO PARA BAIXAR PDF DO MAPA GERAL
            # Preparamos o DataFrame com os nomes de colunas que a função gerar_pdf_relatorio_geral espera
            df_pdf = df_fluxo.copy()
            df_pdf = df_pdf.rename(columns={
                'numero_op': 'Nº OP',
                'cliente': 'Cliente',
                'equipamento': 'Máquina',
                'responsavel_setor': 'Líder',
                'data_entrega': 'Entrega',
                'progresso': 'Progresso %'
            })

            pdf_data = gerar_pdf_relatorio_geral(df_pdf)
            st.download_button(
                label="📥 Baixar Mapa Geral de Produção (PDF)",
                data=pdf_data,
                file_name=f"mapa_producao_santa_cruz_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

            st.divider()

            # 5. GRÁFICOS E VISUALIZAÇÃO
            col_esq, col_dir = st.columns(2)

            with col_esq:
                st.subheader("👥 Carga por Líder")
                fig_pizza = px.pie(df_fluxo, names='responsavel_setor', hole=0.3)
                st.plotly_chart(fig_pizza, use_container_width=True)

            with col_dir:
                st.subheader("📈 Progresso Médio")
                # Gráfico simples de barras para ver quem está mais adiantado
                fig_bar = px.bar(df_fluxo, x='numero_op', y='progresso', color='responsavel_setor',
                                 labels={'numero_op': 'Nº OP', 'progresso': 'Progresso (%)'})
                st.plotly_chart(fig_bar, use_container_width=True)

            st.divider()

            # 6. TABELA DETALHADA
            st.subheader("📋 Tabela de Acompanhamento em Tempo Real")
            # Selecionamos apenas colunas importantes para não poluir a tela
            colunas_view = ['numero_op', 'cliente', 'equipamento', 'responsavel_setor', 'data_entrega', 'progresso']
            st.dataframe(
                df_fluxo[colunas_view],
                use_container_width=True,
                hide_index=True
            )

    else:
        st.info("A planilha do Google está vazia. Cadastre uma OP para gerar o relatório.")




