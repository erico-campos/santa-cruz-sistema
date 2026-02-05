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

# --- NAVEGAÇÃO COM REDIRECIONAMENTO ---

opcoes = ["📋 Lista de OPs", "📊 Relatório"]

# Se for ADM, ele vê o botão de criar do zero no menu
if st.session_state.nivel == "ADM":
    opcoes.insert(1, "➕ Nova OP")
    opcoes.append("⚙️ Configurações")

# Se for LIDER e estiver editando, precisamos permitir que ele entre na página oculta
elif st.session_state.nivel == "LIDER" and st.session_state.edit_op_id is not None:
    opcoes.insert(1, "➕ Nova OP")

# Lógica para mudar de página sozinho ao editar
if st.session_state.edit_op_id is not None:
    menu_index = 1  # Índice da "➕ Nova OP"
else:
    menu_index = 0

menu = st.sidebar.radio("Navegação", opcoes, index=menu_index)

# --- CONFIGURAÇÕES ---
if menu == "⚙️ Configurações":
    st.header("⚙️ Configurações do Sistema")
    t1, t2, t3 = st.tabs(["🏗️ Máquinas", "👷 Líderes", "🔑 Usuários"])

    with t1:
        st.subheader("Gerenciar Máquinas")

        # Busca dados se estiver em modo de edição
        val_n, val_c = "", ""
        if st.session_state.edit_maq_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT nome, conjuntos FROM maquinas WHERE id=?",
                                   (st.session_state.edit_maq_id,)).fetchone()
                if res:
                    val_n, val_c = res[0], res[1]

        with st.form("fm_maq"):
            n = st.text_input("Nome da Máquina", value=val_n)
            c = st.text_area("Checklist / Conjuntos (Separe por vírgula)", value=val_c)

            c_m1, c_m2 = st.columns(2)
            if c_m1.form_submit_button("ATUALIZAR" if st.session_state.edit_maq_id else "SALVAR MÁQUINA"):
                with sqlite3.connect('fabrica_master.db') as conn:
                    if st.session_state.edit_maq_id:
                        conn.execute("UPDATE maquinas SET nome=?, conjuntos=? WHERE id=?",
                                     (n, c, st.session_state.edit_maq_id))
                    else:
                        conn.execute("INSERT OR REPLACE INTO maquinas (nome, conjuntos) VALUES (?,?)", (n, c))
                st.session_state.edit_maq_id = None
                st.rerun()

            if c_m2.form_submit_button("CANCELAR / NOVO"):
                st.session_state.edit_maq_id = None
                st.rerun()

        st.write("### Máquinas Cadastradas")
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
    with t2:
        st.subheader("Gerenciar Líderes")
        with sqlite3.connect('fabrica_master.db') as conn:
            s_df = pd.read_sql_query("SELECT * FROM setores", conn)
        val_nl = ""
        if st.session_state.edit_lid_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT nome FROM setores WHERE id=?", (st.session_state.edit_lid_id,)).fetchone()
                if res: val_nl = res[0]
        with st.form("f_lid"):
            nl = st.text_input("Nome Líder", value=val_nl)
            cl, pl = st.text_input("Cargo"), st.text_input("Senha", type="password")
            if st.form_submit_button("SALVAR"):
                with sqlite3.connect('fabrica_master.db') as conn:
                    if st.session_state.edit_lid_id:
                        conn.execute("UPDATE setores SET nome=? WHERE id=?", (nl.upper(), st.session_state.edit_lid_id))
                    else:
                        conn.execute("INSERT OR IGNORE INTO setores (nome) VALUES (?)", (nl.upper(),))
                        conn.execute("INSERT INTO usuarios (usuario, senha, cargo, ativo) VALUES (?,?,?,0)",
                                     (nl, pl, cl))
                st.session_state.edit_lid_id = None;
                st.rerun()
        for _, s in s_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.write(f"👷 {s['nome']}")
                if c2.button("✏️", key=f"ed_s_{s['id']}"): st.session_state.edit_lid_id = s['id']; st.rerun()
                if c3.button("🗑️", key=f"ds_{s['id']}"):
                    with sqlite3.connect('fabrica_master.db') as conn: conn.execute("DELETE FROM setores WHERE id=?",
                                                                                    (s['id'],)); st.rerun()
    with t3:
        st.subheader("Gerenciar Usuários")

        # 1. LOGICA DE EDIÇÃO
        val_u, val_c = "", ""
        if st.session_state.edit_usr_id:
            with sqlite3.connect('fabrica_master.db') as conn:
                res = conn.execute("SELECT usuario, cargo FROM usuarios WHERE id=?",
                                   (st.session_state.edit_usr_id,)).fetchone()
                if res:
                    val_u, val_c = res[0], res[1]

        # 2. FORMULÁRIO COM CARGO LIVRE (TEXT_INPUT)
        with st.form("form_usuarios_livre"):
            st.write("📝 **Configuração de Acesso Manual**")
            u_nome = st.text_input("Nome de Usuário", value=val_u)
            u_senha = st.text_input("Senha", type="password",
                                    help="Digite a senha para novo usuário ou para alterar a atual")

            # MUDANÇA AQUI: De selectbox para text_input para liberdade total
            u_cargo = st.text_input("Cargo / Setor (Digite o que desejar)", value=val_c)

            c_u1, c_u2 = st.columns(2)
            if c_u1.form_submit_button("💾 SALVAR ALTERAÇÕES" if st.session_state.edit_usr_id else "🚀 CADASTRAR AGORA"):
                if u_nome and (u_senha or st.session_state.edit_usr_id):
                    # Padronizamos para maiúsculas para evitar confusão no login/relatórios
                    cargo_final = u_cargo.upper()

                    with sqlite3.connect('fabrica_master.db') as conn:
                        if st.session_state.edit_usr_id:
                            if u_senha:
                                conn.execute("UPDATE usuarios SET usuario=?, senha=?, cargo=? WHERE id=?",
                                             (u_nome, u_senha, cargo_final, st.session_state.edit_usr_id))
                            else:
                                conn.execute("UPDATE usuarios SET usuario=?, cargo=? WHERE id=?",
                                             (u_nome, cargo_final, st.session_state.edit_usr_id))
                        else:
                            conn.execute("INSERT INTO usuarios (usuario, senha, cargo, ativo) VALUES (?,?,?,1)",
                                         (u_nome, u_senha, cargo_final))

                    st.session_state.edit_usr_id = None
                    st.success(f"Usuário {u_nome} salvo com o cargo: {cargo_final}")
                    st.rerun()
                else:
                    st.error("Nome de usuário e Cargo são obrigatórios.")

            if c_u2.form_submit_button("➕ LIMPAR / NOVO"):
                st.session_state.edit_usr_id = None
                st.rerun()

        st.divider()

        # 3. LISTAGEM DE USUÁRIOS
        st.write("### 👥 Usuários no Sistema")
        with sqlite3.connect('fabrica_master.db') as conn:
            u_df = pd.read_sql_query("SELECT id, usuario, cargo, ativo FROM usuarios", conn)

        for _, u in u_df.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                stt = "🟢" if u['ativo'] == 1 else "🔴"
                col1.write(f"**{u['usuario']}**")
                col1.caption(f"Cargo Definido: {u['cargo']} | Status: {stt}")

                if col2.button("🔄", key=f"tu_{u['id']}", help="Ativar/Inativar"):
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("UPDATE usuarios SET ativo=? WHERE id=?", (0 if u['ativo'] == 1 else 1, u['id']))
                    st.rerun()

                if col3.button("✏️", key=f"ed_u_{u['id']}", help="Editar Cadastro"):
                    st.session_state.edit_usr_id = u['id']
                    st.rerun()

                if col4.button("🗑️", key=f"du_{u['id']}", help="Excluir"):
                    if u['usuario'] != "admsantacruz":
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("DELETE FROM usuarios WHERE id=?", (u['id'],))
                        st.rerun()

elif menu == "➕ Nova OP":
    edit_mode = st.session_state.edit_op_id is not None

    # 1. CARREGAMENTO DE DADOS EM MODO DE EDIÇÃO
    if edit_mode and not st.session_state.layout_confirmado:
        with sqlite3.connect('fabrica_master.db') as conn:
            conn.row_factory = sqlite3.Row
            op_para_editar = conn.execute("SELECT * FROM ordens WHERE id=?", (st.session_state.edit_op_id,)).fetchone()
            if op_para_editar:
                st.session_state.maq_atual = op_para_editar['equipamento']
                st.session_state.campos_dinamicos = json.loads(op_para_editar['info_adicionais_ficha'])
                st.session_state.nomes_specs = list(st.session_state.campos_dinamicos.keys())
                st.session_state.layout_confirmado = True

    st.header("✏️ Editar Ordem de Produção" if edit_mode else "➕ Lançar Nova OP")

    # --- PASSO 1: DEFINIÇÃO DA ESTRUTURA DA FICHA ---
    if not st.session_state.layout_confirmado:
        st.subheader("Passo 1: Definir Estrutura da Ficha")

        # Inicializa lista padrão se estiver vazio
        if 'nomes_specs' not in st.session_state or not st.session_state.nomes_specs:
            st.session_state.nomes_specs = ["Alimentação", "Frascos", "Produto", "Bicos", "Produção", "Estrutura"]

        for i, nome_atual in enumerate(st.session_state.nomes_specs):
            c_ed1, c_ed2 = st.columns([5, 1])
            novo_nome = c_ed1.text_input(f"Campo {i + 1}", value=nome_atual, key=f"n_spec_{i}")
            st.session_state.nomes_specs[i] = novo_nome
            if c_ed2.button("🗑️", key=f"del_spec_{i}"):
                st.session_state.nomes_specs.pop(i)
                st.rerun()

        if st.button("➕ Adicionar Novo Campo"):
            st.session_state.nomes_specs.append("Novo Campo")
            st.rerun()

        st.divider()

        # Seleção da Máquina (Checklist vinculado)
        with sqlite3.connect('fabrica_master.db') as conn:
            lista_maquinas = [m[0] for m in conn.execute("SELECT nome FROM maquinas").fetchall()]

        st.session_state.maq_atual = st.selectbox("Selecione o Equipamento para esta OP", lista_maquinas)

        if st.button("Confirmar Estrutura e Ir para Dados ➡️"):
            st.session_state.layout_confirmado = True
            st.rerun()

    # --- PASSO 2: CONTEÚDO E SALVAMENTO ---
    else:
        st.subheader(f"Passo 2: Conteúdo da OP - {st.session_state.maq_atual}")

        val = {}
        if edit_mode:
            with sqlite3.connect('fabrica_master.db') as conn:
                conn.row_factory = sqlite3.Row
                res = conn.execute("SELECT * FROM ordens WHERE id=?", (st.session_state.edit_op_id,)).fetchone()
                if res:
                    val = dict(res)

        with st.form("f_final_op"):
            st.markdown("### 📄 Informações Gerais")
            c1, c2, c3 = st.columns(3)
            f_op = c1.text_input("Nº OP", value=val.get('numero_op', ""))
            f_cli = c2.text_input("Cliente", value=val.get('cliente', ""))
            f_cnpj = c3.text_input("CNPJ", value=val.get('cnpj', ""))

            st.markdown("### 📅 Cronograma")
            data_entrega_padrao = date.today()
            if val.get('data_entrega'):
                try:
                    data_entrega_padrao = datetime.strptime(val.get('data_entrega'), '%Y-%m-%d').date()
                except:
                    pass
            f_entrega = st.date_input("Data de Entrega", value=data_entrega_padrao)

            st.markdown("### 🛠️ Especificações Técnicas")
            g3_cols = st.columns(3)
            specs_finais = {}
            for i, nome in enumerate(st.session_state.nomes_specs):
                valor_p = st.session_state.campos_dinamicos.get(nome, "") if edit_mode else ""
                specs_finais[nome] = g3_cols[i % 3].text_input(nome, value=valor_p)

            st.markdown("### 🚛 Dados da Esteira / Logística")
            l1, l2, l3, l4, l5 = st.columns(5)
            f_mat = l1.text_input("Material", value=val.get('est_material', ""))
            f_alt = l2.text_input("Altura", value=val.get('est_altura', ""))
            f_com = l3.text_input("Comprimento", value=val.get('est_comprimento', ""))
            f_lar = l4.text_input("Largura", value=val.get('est_largura', ""))
            f_pla = l5.text_input("Plataforma", value=val.get('est_plataforma', ""))

            st.markdown("### 🏢 Distribuição Interna")
            d1, d2, d3 = st.columns(3)
            with sqlite3.connect('fabrica_master.db') as conn:
                sets = [s[0] for s in conn.execute("SELECT nome FROM setores").fetchall()]

            idx_lid = 0
            if edit_mode and val.get('responsavel_setor') in sets:
                idx_lid = sets.index(val.get('responsavel_setor'))

            f_lider = d1.selectbox("Líder Responsável", sets, index=idx_lid)
            f_vend = d2.text_input("Vendedor", value=val.get('dist_vendedor', ""))
            f_revi = d3.text_input("Revisor", value=val.get('dist_revisor', ""))

            d4, d5, d6, d7 = st.columns(4)
            f_pcp = d4.text_input("PCP", value=val.get('dist_pcp', ""))
            f_proj = d5.text_input("Projeto", value=val.get('dist_projeto', ""))
            f_elet = d6.text_input("Elétrica", value=val.get('dist_eletrica', ""))
            f_mont = d7.text_input("Montagem", value=val.get('dist_montagem', ""))

            f_info = st.text_area("Observações Adicionais", value=val.get('ast_instalacao', ""))

            submit = st.form_submit_button("💾 FINALIZAR E SALVAR OP")

            if submit:
                with sqlite3.connect('fabrica_master.db') as conn:
                    specs_json = json.dumps(specs_finais)
                    if edit_mode:
                        conn.execute("""UPDATE ordens SET 
                            numero_op=?, cliente=?, cnpj=?, data_entrega=?,
                            est_material=?, est_altura=?, est_comprimento=?, est_largura=?, est_plataforma=?,
                            responsavel_setor=?, dist_vendedor=?, dist_revisor=?, dist_pcp=?, 
                            dist_projeto=?, dist_eletrica=?, dist_montagem=?,
                            ast_instalacao=?, info_adicionais_ficha=? WHERE id=?""",
                                     (f_op, f_cli, f_cnpj, str(f_entrega), f_mat, f_alt, f_com, f_lar, f_pla,
                                      f_lider, f_vend, f_revi, f_pcp, f_proj, f_elet, f_mont, f_info, specs_json,
                                      st.session_state.edit_op_id))
                    else:
                        conn.execute("""INSERT INTO ordens (
                            numero_op, cliente, cnpj, data_entrega, est_material, est_altura, est_comprimento, 
                            est_largura, est_plataforma, responsavel_setor, dist_vendedor, dist_revisor, 
                            dist_pcp, dist_projeto, dist_eletrica, dist_montagem, ast_instalacao, 
                            info_adicionais_ficha, data_op, equipamento, progresso, status
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                     (f_op, f_cli, f_cnpj, str(f_entrega), f_mat, f_alt, f_com, f_lar, f_pla,
                                      f_lider, f_vend, f_revi, f_pcp, f_proj, f_elet, f_mont, f_info, specs_json,
                                      str(date.today()), st.session_state.maq_atual, 0, 'Em Produção'))

                st.session_state.layout_confirmado = False
                st.session_state.edit_op_id = None
                st.success("✅ Ordem de Produção salva com sucesso!")
                st.rerun()

        if st.button("⬅️ Voltar / Cancelar"):
            st.session_state.layout_confirmado = False
            st.session_state.edit_op_id = None
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
        # Removido filtros restritivos para que as OPs novas apareçam imediatamente
        ops = conn.execute("SELECT * FROM ordens ORDER BY id DESC").fetchall()

        # Busca cargos ativos para o sistema de mensagens (Acompanhamento)
        res_cargos = conn.execute("SELECT DISTINCT cargo FROM usuarios WHERE ativo=1").fetchall()
        cargos_chat = [c[0] for c in res_cargos]

    if not ops:
        st.info("Nenhuma Ordem de Produção encontrada. Vá em 'Nova OP' para cadastrar.")

    for op in ops:
        # Lógica de cores baseada na data de entrega
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

        # Cabeçalho do Card da OP
        with st.expander(f"{cor_alerta} OP {op['numero_op']} - {op['cliente']} | Entrega: {op['data_entrega']}"):
            t1, t2, t3 = st.tabs(["Ficha Técnica", "Checklist", "Acompanhamento"])

            with t1:
                # --- 1. ALERTAS VISUAIS ---
                if cor_alerta == "🔴":
                    st.error(f"🚨 **URGENTE:** Entrega em {dias_restantes} dias!")
                elif cor_alerta == "🟡":
                    st.warning(f"⚠️ **ATENÇÃO:** Entrega em {dias_restantes} dias.")

                # --- 2. DADOS GERAIS ---
                st.subheader("📄 Dados do Projeto")
                c_g1, c_g2, c_g3 = st.columns(3)
                c_g1.write(f"**Nº OP:** {op['numero_op']}")
                c_g1.write(f"**Cliente:** {op['cliente']}")
                c_g2.write(f"**Equipamento:** {op['equipamento']}")
                c_g2.write(f"**CNPJ:** {op['cnpj']}")
                c_g3.write(f"**Emissão:** {op['data_op']}")
                c_g3.write(f"**Entrega:** {op['data_entrega']}")

                st.divider()

                # --- 3. ESPECIFICAÇÕES DINÂMICAS ---
                st.subheader("🛠️ Especificações Técnicas")
                try:
                    specs = json.loads(op['info_adicionais_ficha'])
                    cols_specs = st.columns(3)
                    for i, (campo, valor) in enumerate(specs.items()):
                        cols_specs[i % 3].write(f"**{campo}:** {valor}")
                except:
                    st.error("Erro ao carregar dados técnicos.")

                st.divider()

                # --- 4. LOGÍSTICA E DISTRIBUIÇÃO ---
                st.subheader("🚛 Logística e Fábrica")
                l1, l2, l3 = st.columns(3)
                l1.write(f"**Material:** {op['est_material']}")
                l1.write(f"**Altura:** {op['est_altura']}")
                l2.write(f"**Comprimento:** {op['est_comprimento']}")
                l2.write(f"**Largura:** {op['est_largura']}")
                l3.write(f"**Plataforma:** {op['est_plataforma']}")
                l3.write(f"**Líder Responsável:** {op['responsavel_setor']}")

                d_log1, d_log2, d_log3 = st.columns(3)
                d_log1.write(f"**Vendedor:** {op['dist_vendedor']}")
                d_log1.write(f"**PCP:** {op['dist_pcp']}")
                d_log2.write(f"**Revisor:** {op['dist_revisor']}")
                d_log2.write(f"**Projeto:** {op['dist_projeto']}")
                d_log3.write(f"**Elétrica:** {op['dist_eletrica']}")
                d_log3.write(f"**Montagem:** {op['dist_montagem']}")

                st.info(f"**🔧 Obs/Assistência:** {op['ast_instalacao']}")

                st.divider()

                # --- 5. ANEXOS ---
                st.subheader("📁 Arquivos")
                if op['anexo']:
                    caminho_arq = os.path.join("anexos", op['anexo'])
                    if os.path.exists(caminho_arq):
                        c_a1, c_a2 = st.columns(2)
                        with open(caminho_arq, "rb") as f:
                            c_a1.download_button("📥 Baixar Anexo", f, file_name=op['anexo'], key=f"dl_{op['id']}")
                        if c_a2.button("🗑️ Excluir Anexo", key=f"rm_an_{op['id']}"):
                            with sqlite3.connect('fabrica_master.db') as conn:
                                conn.execute("UPDATE ordens SET anexo=NULL WHERE id=?", (op['id'],))
                            if os.path.exists(caminho_arq): os.remove(caminho_arq)
                            st.rerun()

                arquivo_upload = st.file_uploader("Upload de Foto/PDF", type=["pdf", "png", "jpg", "jpeg"],
                                                  key=f"up_{op['id']}")
                if arquivo_upload:
                    nome_arq = f"OP_{op['numero_op']}_{arquivo_upload.name}".replace(" ", "_")
                    caminho_salvar = os.path.join("anexos", nome_arq)
                    with open(caminho_salvar, "wb") as f:
                        f.write(arquivo_upload.getbuffer())
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("UPDATE ordens SET anexo=? WHERE id=?", (nome_arq, op['id']))
                    st.success("Anexo Salvo!")
                    st.rerun()

                st.divider()


                # --- 6. BOTÕES DE AÇÃO (PDF, EDITAR E EXCLUIR) ---
                c_pdf, c_edit, c_del = st.columns(3)

                # Botão PDF (Todos veem)
                c_pdf.download_button(
                    label="📂 Gerar PDF",
                    data=gerar_pdf_op(op),
                    file_name=f"OP_{op['numero_op']}.pdf",
                    key=f"pdf_btn_{op['id']}",
                    use_container_width=True
                )

                # Botão Editar (LIBERADO PARA ADM, PCP E LIDER)
                # Verificamos se o nível não é 'USER' (Vendedores/Visitantes)
                if st.session_state.nivel in ["ADM", "LIDER"]:
                    if c_edit.button("✏️ Editar OP", key=f"edit_btn_{op['id']}", use_container_width=True):
                        st.session_state.edit_op_id = op['id']
                        st.session_state.maq_atual = op['equipamento']
                        specs_salvas = json.loads(op['info_adicionais_ficha'])
                        st.session_state.campos_dinamicos = specs_salvas
                        st.session_state.nomes_specs = list(specs_salvas.keys())
                        st.session_state.layout_confirmado = True
                        st.rerun()

                # Botão Excluir (CONTINUA APENAS PARA ADM)
                if st.session_state.nivel == "ADM":
                    if c_del.button("🗑️ Excluir OP", key=f"del_op_{op['id']}", use_container_width=True):
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("DELETE FROM ordens WHERE id=?", (op['id'],))
                        st.success("Removido!")
                        st.rerun()

            with t2:
                # Checklist de Montagem
                with sqlite3.connect('fabrica_master.db') as conn:
                    m = conn.execute("SELECT conjuntos FROM maquinas WHERE nome=?", (op['equipamento'],)).fetchone()

                itens_checklist = [i.strip() for i in m[0].split(",")] if m and m[0] else []
                concluidos = op['checks_concluidos'].split("|") if op['checks_concluidos'] else []

                if itens_checklist:
                    selecionados = [i for i in itens_checklist if
                                    st.checkbox(i, i in concluidos, key=f"ck_{op['id']}_{i}")]
                    if st.button("💾 Atualizar Progresso", key=f"sck_{op['id']}"):
                        percentual = int((len(selecionados) / len(itens_checklist)) * 100)
                        status_texto = "Concluído" if percentual == 100 else "Em Produção"
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("UPDATE ordens SET progresso=?, checks_concluidos=?, status=? WHERE id=?",
                                         (percentual, "|".join(selecionados), status_texto, op['id']))
                        st.success(f"Progresso de {percentual}% salvo!")
                        st.rerun()
                else:
                    st.warning("Nenhum checklist cadastrado para esta máquina nas Configurações.")

            with t3:
                # Sistema de Logs/Chat Interno
                logs = json.loads(op['acompanhamento_log'])
                with st.form(f"chat_form_{op['id']}"):
                    destinatario = st.selectbox("Enviar para:", cargos_chat)
                    mensagem = st.text_area("Escrever mensagem...")
                    if st.form_submit_button("Enviar Mensagem"):
                        logs.append({
                            "cargo_destino": destinatario,
                            "user_origem": st.session_state.user_logado,
                            "data": datetime.now().strftime("%d/%m %H:%M"),
                            "msg": mensagem
                        })
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("UPDATE ordens SET acompanhamento_log=? WHERE id=?",
                                         (json.dumps(logs), op['id']))
                        st.rerun()

                for msg_log in reversed(logs):
                    st.chat_message(
                        "user" if msg_log['user_origem'] == st.session_state.user_logado else "assistant").write(
                        f"**{msg_log['user_origem']}** para **{msg_log['cargo_destino']}** ({msg_log.get('data', '')})\n\n{msg_log['msg']}"
                    )


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
