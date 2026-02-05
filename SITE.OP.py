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
    edit_mode = st.session_state.edit_op_id is not None

    # 1. CARREGAMENTO DE DADOS PARA EDIÇÃO
    if edit_mode and not st.session_state.layout_confirmado:
        with sqlite3.connect('fabrica_master.db') as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT * FROM ordens WHERE id=?", (st.session_state.edit_op_id,)).fetchone()
            if res:
                st.session_state.maq_atual = res['equipamento']
                st.session_state.campos_dinamicos = json.loads(res['info_adicionais_ficha'])
                st.session_state.nomes_specs = list(st.session_state.campos_dinamicos.keys())
                st.session_state.layout_confirmado = True

    st.header("✏️ Editar Ficha Técnica" if edit_mode else "➕ Lançar Nova OP")

    # --- PASSO 1: ESTRUTURA TÉCNICA (DINÂMICA) ---
    if not st.session_state.layout_confirmado:
        st.subheader("Passo 1: Definir Especificações da Máquina")
        st.info("Adicione ou remova campos conforme a necessidade deste equipamento.")

        if 'nomes_specs' not in st.session_state:
            st.session_state.nomes_specs = ["Alimentação", "Frasco", "Amostra", "Bicos", "Produto", "Estrutura"]

        # Interface para incluir/excluir especificações
        for i, nome in enumerate(st.session_state.nomes_specs):
            c_ed1, c_ed2 = st.columns([5, 1])
            st.session_state.nomes_specs[i] = c_ed1.text_input(f"Especificação {i + 1}", value=nome,
                                                               key=f"spec_name_{i}")
            if c_ed2.button("🗑️", key=f"del_spec_{i}"):
                st.session_state.nomes_specs.pop(i)
                st.rerun()

        if st.button("➕ Incluir Mais Especificações"):
            st.session_state.nomes_specs.append("Novo Campo")
            st.rerun()

        st.divider()
        with sqlite3.connect('fabrica_master.db') as conn:
            maqs = [m[0] for m in conn.execute("SELECT nome FROM maquinas").fetchall()]
        st.session_state.maq_atual = st.selectbox("Selecione o Equipamento Base", maqs)

        if st.button("Ir para Preenchimento de Dados ➡️"):
            st.session_state.layout_confirmado = True
            st.rerun()

    # --- PASSO 2: PREENCHIMENTO COMPLETO ---
    else:
        st.subheader(f"Passo 2: Detalhes da OP - {st.session_state.maq_atual}")

        val = {}
        if edit_mode:
            with sqlite3.connect('fabrica_master.db') as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM ordens WHERE id=?", (st.session_state.edit_op_id,)).fetchone()
                if row: val = dict(row)

        with st.form("form_op_completa"):
            # BLOCO 1: DADOS DA OP
            st.markdown("#### 📄 Dados da Ordem de Produção")
            c1, c2, c3 = st.columns(3)
            f_op = c1.text_input("N° OP", value=val.get('numero_op', ""))
            f_cli = c2.text_input("Cliente", value=val.get('cliente', ""))
            f_data_op = c3.date_input("Data da OP", value=date.today())

            c4, c5 = st.columns(2)
            f_entrega = c4.date_input("Data de Entrega",
                                      value=date.today() if not val.get('data_entrega') else datetime.strptime(
                                          val.get('data_entrega'), '%Y-%m-%d').date())
            f_vend_op = c5.text_input("Vendedor (OP)", value=val.get('vendedor', ""))

            # BLOCO 2: DADOS DO CLIENTE
            st.markdown("#### 👥 Dados do Cliente")
            cc1, cc2 = st.columns(2)
            f_cnpj = cc1.text_input("CNPJ", value=val.get('cnpj', ""))
            f_end = cc2.text_input("Endereço Completo", value=val.get('exp_endereco', ""))

            # BLOCO 3: ESPECIFICAÇÕES TÉCNICAS (DINÂMICAS)
            st.markdown("#### 🛠️ Especificações da Máquina")
            g_specs = st.columns(3)
            specs_finais = {}
            for i, nome in enumerate(st.session_state.nomes_specs):
                v_pre = st.session_state.campos_dinamicos.get(nome, "")
                specs_finais[nome] = g_specs[i % 3].text_input(nome, value=v_pre)

            # BLOCO 4: DADOS DA ESTEIRA
            st.markdown("#### 🚛 Dados da Esteira")
            e1, e2, e3, e4, e5 = st.columns(5)
            f_mat = e1.text_input("Material", value=val.get('est_material', ""))
            f_alt = e2.text_input("Altura", value=val.get('est_altura', ""))
            f_com = e3.text_input("Comprimento", value=val.get('est_comprimento', ""))
            f_lar = e4.text_input("Largura", value=val.get('est_largura', ""))
            f_pla = e5.text_input("Plataforma", value=val.get('est_plataforma', ""))

            # BLOCO 5: DISTRIBUIÇÃO INTERNA
            st.markdown("#### 🏢 Distribuição Interna")
            d1, d2, d3 = st.columns(3)
            f_dist_vend = d1.text_input("Vendedor (Distribuição)", value=val.get('dist_vendedor', ""))
            f_revi = d2.text_input("Revisor", value=val.get('dist_revisor', ""))
            f_pcp = d3.text_input("PCP", value=val.get('dist_pcp', ""))

            d4, d5, d6 = st.columns(3)
            f_proj = d4.text_input("Projeto", value=val.get('dist_projeto', ""))
            f_elet = d5.text_input("Elétrica", value=val.get('dist_eletrica', ""))
            f_mont = d6.text_input("Montagem", value=val.get('dist_montagem', ""))

            st.markdown("#### 📝 Finalização")
            f_info = st.text_area("Informações Adicionais", value=val.get('ast_instalacao', ""))

            with sqlite3.connect('fabrica_master.db') as conn:
                lista_lideres = [s[0] for s in conn.execute("SELECT nome FROM setores").fetchall()]
            f_lider = st.selectbox("Líder do Setor (Responsável)", lista_lideres)

            # SALVAMENTO
            submit = st.form_submit_button("💾 SALVAR E FINALIZAR OP")

            if submit:
                with sqlite3.connect('fabrica_master.db') as conn:
                    specs_json = json.dumps(specs_finais)
                    if edit_mode:
                        conn.execute("""UPDATE ordens SET 
                            numero_op=?, cliente=?, data_op=?, data_entrega=?, vendedor=?, 
                            cnpj=?, exp_endereco=?, info_adicionais_ficha=?, 
                            est_material=?, est_altura=?, est_comprimento=?, est_largura=?, est_plataforma=?,
                            dist_vendedor=?, dist_revisor=?, dist_pcp=?, dist_projeto=?, dist_eletrica=?, dist_montagem=?,
                            ast_instalacao=?, responsavel_setor=? WHERE id=?""",
                                     (f_op, f_cli, str(f_data_op), str(f_entrega), f_vend_op, f_cnpj, f_end, specs_json,
                                      f_mat, f_alt, f_com, f_lar, f_pla, f_dist_vend, f_revi, f_pcp, f_proj, f_elet,
                                      f_mont,
                                      f_info, f_lider, st.session_state.edit_op_id))
                    else:
                        conn.execute("""INSERT INTO ordens (
                            numero_op, cliente, data_op, data_entrega, vendedor, cnpj, exp_endereco, 
                            info_adicionais_ficha, est_material, est_altura, est_comprimento, est_largura, est_plataforma,
                            dist_vendedor, dist_revisor, dist_pcp, dist_projeto, dist_eletrica, dist_montagem,
                            ast_instalacao, responsavel_setor, equipamento, progresso, status
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                     (f_op, f_cli, str(f_data_op), str(f_entrega), f_vend_op, f_cnpj, f_end, specs_json,
                                      f_mat, f_alt, f_com, f_lar, f_pla, f_dist_vend, f_revi, f_pcp, f_proj, f_elet,
                                      f_mont,
                                      f_info, f_lider, st.session_state.maq_atual, 0, 'Em Produção'))

                st.session_state.edit_op_id = None
                st.session_state.layout_confirmado = False
                st.success("OP salva com sucesso!")
                st.rerun()

        if st.button("⬅️ Cancelar"):
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

if menu == "📋 Lista de OPs":
    with sqlite3.connect('fabrica_master.db') as conn:
        conn.row_factory = sqlite3.Row

        # Query especial que extrai o número após o "SC-" para ordenar matematicamente
        query = """
            SELECT * FROM ordens 
            ORDER BY CAST(SUBSTR(numero_op, INSTR(numero_op, '-') + 1) AS INTEGER) DESC
        """
        ops = conn.execute(query).fetchall()

        # Busca cargos ativos para o chat/acompanhamento
        res_cargos = conn.execute("SELECT DISTINCT cargo FROM usuarios WHERE ativo=1").fetchall()
        cargos_chat = [c[0] for c in res_cargos]

    if not ops:
        st.info("Nenhuma Ordem de Produção encontrada.")

    for op in ops:
        # --- 1. LÓGICA DE CORES POR DATA ---
        hoje = date.today()
        cor_alerta = "⚪"
        try:
            entrega = datetime.strptime(op['data_entrega'], '%Y-%m-%d').date()
            dias_restantes = (entrega - hoje).days
            if dias_restantes > 30:
                cor_alerta = "🟢"
            elif 15 <= dias_restantes <= 30:
                cor_alerta = "🟡"
            else:
                cor_alerta = "🔴"
        except:
            dias_restantes = "N/A"

        # --- 2. CABEÇALHO DO CARD ---
        with st.expander(f"{cor_alerta} OP {op['numero_op']} - {op['cliente']} | Entrega: {op['data_entrega']}"):
            t1, t2, t3 = st.tabs(["📄 Ficha Técnica", "✅ Checklist", "💬 Acompanhamento"])

            with t1:
                # Dados Gerais
                st.subheader("Dados do Projeto")
                c_g1, c_g2, c_g3 = st.columns(3)
                c_g1.write(f"**Nº OP:** {op['numero_op']}")
                c_g1.write(f"**Cliente:** {op['cliente']}")
                c_g2.write(f"**Equipamento:** {op['equipamento']}")
                c_g2.write(f"**CNPJ:** {op['cnpj']}")
                c_g3.write(f"**Emissão:** {op['data_op']}")
                c_g3.write(f"**Entrega:** {op['data_entrega']}")

                st.divider()

                # Especificações Técnicas Dinâmicas
                st.subheader("🛠️ Especificações Técnicas")
                try:
                    specs = json.loads(op['info_adicionais_ficha'])
                    cols_specs = st.columns(3)
                    for i, (campo, valor) in enumerate(specs.items()):
                        cols_specs[i % 3].write(f"**{campo}:** {valor}")
                except:
                    st.error("Erro ao carregar dados técnicos.")

                st.divider()

                # Distribuição e Fábrica
                st.subheader("🏢 Distribuição e Fábrica")
                d_log1, d_log2, d_log3 = st.columns(3)
                d_log1.write(f"**Revisor:** {op['dist_revisor']}")
                d_log1.write(f"**PCP:** {op['dist_pcp']}")
                d_log2.write(f"**Projeto:** {op['dist_projeto']}")
                d_log2.write(f"**Montagem:** {op['dist_montagem']}")
                d_log3.write(f"**Líder:** {op['responsavel_setor']}")
                st.info(f"**🔧 Observações:** {op['ast_instalacao']}")

                st.divider()

                # --- 3. ANEXOS ---
                st.subheader("📁 Arquivos e Fotos")
                if op['anexo']:
                    caminho_arq = os.path.join("anexos", op['anexo'])
                    if os.path.exists(caminho_arq):
                        c_at1, c_at2 = st.columns([1, 4])
                        with open(caminho_arq, "rb") as f:
                            c_at1.download_button("📥 Baixar", f, file_name=op['anexo'], key=f"dl_{op['id']}")
                        if st.session_state.nivel == "ADM":
                            if c_at2.button("🗑️ Excluir Arquivo", key=f"rm_an_{op['id']}"):
                                with sqlite3.connect('fabrica_master.db') as conn:
                                    conn.execute("UPDATE ordens SET anexo=NULL WHERE id=?", (op['id'],))
                                st.rerun()

                arquivo_upload = st.file_uploader("Upload de novo anexo", type=["pdf", "png", "jpg", "jpeg"],
                                                  key=f"up_{op['id']}")
                if arquivo_upload:
                    nome_arq = f"OP_{op['numero_op']}_{arquivo_upload.name}".replace(" ", "_")
                    with open(os.path.join("anexos", nome_arq), "wb") as f:
                        f.write(arquivo_upload.getbuffer())
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("UPDATE ordens SET anexo=? WHERE id=?", (nome_arq, op['id']))
                    st.success("Anexo Salvo!")
                    st.rerun()

                st.divider()

                # --- 4. BOTÕES DE CONTROLE ---
                c_pdf, c_edit, c_del = st.columns(3)

                # Gerar PDF
                c_pdf.download_button("📂 Gerar PDF", gerar_pdf_op(op), f"OP_{op['numero_op']}.pdf",
                                      key=f"pdf_btn_{op['id']}", use_container_width=True)

                # EDITAR (ADM e LIDER)
                if st.session_state.nivel in ["ADM", "LIDER"]:
                    if c_edit.button("✏️ Editar Ficha", key=f"edit_btn_{op['id']}", use_container_width=True):
                        st.session_state.edit_op_id = op['id']
                        st.session_state.maq_atual = op['equipamento']
                        specs_salvas = json.loads(op['info_adicionais_ficha'])
                        st.session_state.campos_dinamicos = specs_salvas
                        st.session_state.nomes_specs = list(specs_salvas.keys())
                        st.session_state.layout_confirmado = True
                        st.rerun()

                # EXCLUIR (Apenas ADM)
                if st.session_state.nivel == "ADM":
                    if c_del.button("🗑️ Excluir OP", key=f"del_op_{op['id']}", use_container_width=True):
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("DELETE FROM ordens WHERE id=?", (op['id'],))
                        st.rerun()

            with t2:
                # --- CHECKLIST ---
                with sqlite3.connect('fabrica_master.db') as conn:
                    m = conn.execute("SELECT conjuntos FROM maquinas WHERE nome=?", (op['equipamento'],)).fetchone()
                itens = [i.strip() for i in m[0].split(",")] if m and m[0] else []
                concluidos = op['checks_concluidos'].split("|") if op['checks_concluidos'] else []
                if itens:
                    sel = [i for i in itens if st.checkbox(i, i in concluidos, key=f"ck_{op['id']}_{i}")]
                    if st.button("💾 Salvar Checklist", key=f"sck_{op['id']}"):
                        perc = int((len(sel) / len(itens)) * 100)
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("UPDATE ordens SET progresso=?, checks_concluidos=?, status=? WHERE id=?",
                                         (perc, "|".join(sel), "Concluído" if perc == 100 else "Em Produção", op['id']))
                        st.success(f"Progresso de {perc}% salvo!")
                        st.rerun()
                else:
                    st.warning("Cadastre o checklist na aba Máquinas.")

            with t3:
                # --- CHAT / LOG ---
                logs = json.loads(op['acompanhamento_log'])
                with st.form(f"chat_form_{op['id']}"):
                    dest = st.selectbox("Para:", cargos_chat)
                    msg = st.text_area("Mensagem...")
                    if st.form_submit_button("Enviar"):
                        logs.append({"cargo_destino": dest, "user_origem": st.session_state.user_logado,
                                     "data": datetime.now().strftime("%d/%m %H:%M"), "msg": msg})
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("UPDATE ordens SET acompanhamento_log=? WHERE id=?",
                                         (json.dumps(logs), op['id']))
                        st.rerun()
                for m_log in reversed(logs):
                    st.chat_message(
                        "user" if m_log['user_origem'] == st.session_state.user_logado else "assistant").write(
                        f"**{m_log['user_origem']}** para **{m_log['cargo_destino']}** ({m_log.get('data', '')})\n\n{m_log['msg']}")


# --- RELATÓRIO DINÂMICO COM GRÁFICO POR LÍDER ---
elif menu == "📊 Relatório":
    st.header("📊 Painel de Controle de Produção")

    with sqlite3.connect('fabrica_master.db') as conn:
        query = """
            SELECT 
                numero_op AS 'Nº OP', 
                cliente AS 'Cliente', 
                equipamento AS 'Máquina', 
                responsavel_setor AS 'Líder', 
                data_entrega AS 'Entrega',
                progresso AS 'Progresso %'
            FROM ordens 
            WHERE progresso > 0 AND progresso < 100
            ORDER BY data_entrega ASC
        """
        df = pd.read_sql_query(query, conn)

    if not df.empty:
        # Métricas de Resumo
        c1, c2, c3 = st.columns(3)
        c1.metric("OPs em Produção", len(df))
        c2.metric("Líderes Ativos", df['Líder'].nunique())

        # --- BOTÃO DO PDF DO RELATÓRIO ---
        pdf_geral = gerar_pdf_relatorio_geral(df)
        st.download_button(
            label="📥 Baixar Relatório Geral em PDF",
            data=pdf_geral,
            file_name=f"relatorio_producao_{date.today()}.pdf",
            mime="application/pdf"
        )
        st.divider()

        # Gráfico de Pizza
        st.subheader("👥 Distribuição por Líder")
        df_pizza = df['Líder'].value_counts().reset_index()
        df_pizza.columns = ['Líder', 'Qtd OPs']
        fig = px.pie(df_pizza, values='Qtd OPs', names='Líder', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Tabela Detalhada
        st.subheader("📋 Detalhamento de OPs em Fluxo")
        st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        st.info("Nenhuma OP em andamento para gerar relatório.")



