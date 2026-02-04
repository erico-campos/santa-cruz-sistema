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


def gerar_pdf_op(op_raw):
    # Converte o objeto do banco em um dicionário real para evitar erros de 'get'
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
    cor_fundo_faixa = colors.HexColor("#1A242F")  # Azul Marinho Escuro
    cor_borda = colors.HexColor("#BDC3C7")  # Cinza Profissional

    estilo_titulo_doc = ParagraphStyle(
        'TituloDoc', parent=styles['Heading1'], fontSize=22, alignment=1, spaceAfter=25, textColor=cor_fundo_faixa
    )

    estilo_secao = ParagraphStyle(
        'Secao', parent=styles['Heading2'], fontSize=15,
        backColor=cor_fundo_faixa, borderPadding=8, spaceBefore=0, spaceAfter=10, borderRadius=2
    )

    estilo_item = ParagraphStyle(
        'ItemTexto', parent=styles['Normal'], fontSize=12, leading=16, textColor=colors.black
    )

    estilo_tabela = TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, cor_borda),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ])

    def titulo_branco(texto):
        return Paragraph(f'<font color="white"><b>{texto}</b></font>', estilo_secao)

    # --- INÍCIO DO CONTEÚDO ---
    elementos.append(Paragraph(f"ORDEM DE PRODUÇÃO - {op.get('numero_op', 'N/A')}", estilo_titulo_doc))

    # --- 1. DADOS DO CLIENTE E PROJETO ---
    bloco1 = []
    bloco1.append(titulo_branco("1. DADOS DO CLIENTE E PROJETO"))
    dados_p = [
        [Paragraph(f"<b>CLIENTE:</b><br/>{op.get('cliente', '')}", estilo_item),
         Paragraph(f"<b>EQUIPAMENTO:</b><br/>{op.get('equipamento', '')}", estilo_item)],
        [Paragraph(f"<b>CNPJ:</b><br/>{op.get('cnpj', '')}", estilo_item),
         Paragraph(f"<b>LÍDER RESPONSÁVEL:</b><br/>{op.get('responsavel_setor', '')}", estilo_item)],
        [Paragraph(f"<b>DATA EMISSÃO:</b><br/>{op.get('data_op', '')}", estilo_item),
         Paragraph(f"<b>DATA ENTREGA:</b><br/>{op.get('data_entrega', '')}", estilo_item)]
    ]
    t1 = Table(dados_p, colWidths=[9 * cm, 9 * cm])
    t1.setStyle(estilo_tabela)
    bloco1.append(t1)
    elementos.append(KeepTogether(bloco1))
    elementos.append(Spacer(1, 0.8 * cm))

    # --- 2. ESPECIFICAÇÕES TÉCNICAS (DINÂMICAS) ---
    bloco2 = []
    bloco2.append(titulo_branco("2. ESPECIFICAÇÕES TÉCNICAS"))
    try:
        specs = json.loads(op.get('info_adicionais_ficha', '{}'))
        itens_tec = [Paragraph(f"<b>{k.upper()}:</b><br/>{v}", estilo_item) for k, v in specs.items()]
        data_tec = []
        for i in range(0, len(itens_tec), 2):
            row = [itens_tec[i], itens_tec[i + 1] if i + 1 < len(itens_tec) else ""]
            data_tec.append(row)
        if data_tec:
            t2 = Table(data_tec, colWidths=[9 * cm, 9 * cm])
            t2.setStyle(estilo_tabela)
            bloco2.append(t2)
            elementos.append(KeepTogether(bloco2))
            elementos.append(Spacer(1, 0.8 * cm))
    except:
        elementos.append(Paragraph("Erro ao carregar especificações técnicas.", estilo_item))

    # --- 3. LOGÍSTICA E DISTRIBUIÇÃO ---
    bloco3 = []
    bloco3.append(titulo_branco("3. LOGÍSTICA E DISTRIBUIÇÃO"))
    log_data = [
        [Paragraph(f"<b>MATERIAL:</b> {op.get('est_material', '')}", estilo_item),
         Paragraph(f"<b>ALTURA:</b> {op.get('est_altura', '')}", estilo_item)],
        [Paragraph(f"<b>COMPRIMENTO:</b> {op.get('est_comprimento', '')}", estilo_item),
         Paragraph(f"<b>LARGURA:</b> {op.get('est_largura', '')}", estilo_item)],
        [Paragraph(f"<b>VENDEDOR:</b> {op.get('dist_vendedor', '')}", estilo_item),
         Paragraph(f"<b>PCP:</b> {op.get('dist_pcp', '')}", estilo_item)],
        [Paragraph(f"<b>REVISOR:</b> {op.get('dist_revisor', '')}", estilo_item),
         Paragraph(f"<b>PROJETO:</b> {op.get('dist_projeto', '')}", estilo_item)],
        [Paragraph(f"<b>ELÉTRICA:</b> {op.get('dist_eletrica', '')}", estilo_item),
         Paragraph(f"<b>MONTAGEM:</b> {op.get('dist_montagem', '')}", estilo_item)]
    ]
    t3 = Table(log_data, colWidths=[9 * cm, 9 * cm])
    t3.setStyle(estilo_tabela)
    bloco3.append(t3)

    t3_obs = Table([
        [Paragraph(f"<b>ENDEREÇO DE ENTREGA:</b><br/>{op.get('exp_endereco', '')}", estilo_item)],
        [Paragraph(f"<b>ASSISTÊNCIA / INSTALAÇÃO:</b><br/>{op.get('ast_instalacao', '')}", estilo_item)]
    ], colWidths=[18 * cm])
    t3_obs.setStyle(estilo_tabela)
    bloco3.append(t3_obs)

    elementos.append(KeepTogether(bloco3))
    elementos.append(Spacer(1, 0.8 * cm))

    # --- 4. ANEXO FOTOGRÁFICO ---
    if op.get('anexo'):
        caminho_foto = os.path.join("anexos", op['anexo'])
        if os.path.exists(caminho_foto):
            ext = op['anexo'].split(".")[-1].lower()
            if ext in ["png", "jpg", "jpeg"]:
                from reportlab.platypus import Image
                elementos.append(PageBreak())
                elementos.append(titulo_branco("4. ANEXO FOTOGRÁFICO"))
                elementos.append(Spacer(1, 0.5 * cm))

                img = Image(caminho_foto)
                largura_max = 16 * cm
                proporcao = largura_max / img.drawWidth
                img.drawWidth = largura_max
                img.drawHeight = img.drawHeight * proporcao

                elementos.append(img)
                elementos.append(Paragraph(f"<center>Arquivo: {op['anexo']}</center>", estilo_item))

    # --- 5. HISTÓRICO DE ACOMPANHAMENTO ---
    elementos.append(PageBreak())
    elementos.append(titulo_branco("5. HISTÓRICO DE ACOMPANHAMENTO"))
    try:
        logs = json.loads(op.get('acompanhamento_log', '[]'))
        if not logs:
            elementos.append(Paragraph("Nenhum registro encontrado.", estilo_item))
        else:
            for l in logs:
                chat_data = [
                    [Paragraph(
                        f"<b>De: {l.get('user_origem', '')} para {l.get('cargo_destino', '')}</b> ({l.get('data_inicio', '')})",
                        estilo_item)],
                    [Paragraph(f"<i>Mensagem:</i> {l.get('msg', '')}", estilo_item)]
                ]
                for h in l.get('historico_conversa', []):
                    chat_data.append([Paragraph(f"&nbsp;&nbsp;&nbsp;↪ <b>{h['autor']}:</b> {h['texto']}", estilo_item)])

                t_log = Table(chat_data, colWidths=[18 * cm])
                t_log.setStyle(estilo_tabela)
                elementos.append(t_log)
                elementos.append(Spacer(1, 0.4 * cm))
    except:
        elementos.append(Paragraph("Erro ao carregar histórico.", estilo_item))

    doc.build(elementos)
    return buffer.getvalue()

# --- LOGIN ---
if not st.session_state.auth:
    st.title("🏭 Login - ERP Produção Master")
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
if st.session_state.nivel == "ADM":
    opcoes.insert(1, "➕ Nova OP")
    opcoes.append("⚙️ Configurações")


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
    # --- LÓGICA DE CARREGAMENTO PARA EDIÇÃO ---
    edit_mode = st.session_state.edit_op_id is not None

    # Se entrou em modo edição e ainda não confirmou layout, fazemos isso automaticamente
    if edit_mode and not st.session_state.layout_confirmado:
        with sqlite3.connect('fabrica_master.db') as conn:
            conn.row_factory = sqlite3.Row
            op_para_editar = conn.execute("SELECT * FROM ordens WHERE id=?", (st.session_state.edit_op_id,)).fetchone()
            if op_para_editar:
                # Carregamos a máquina e as especificações técnicas (JSON)
                st.session_state.maq_atual = op_para_editar['equipamento']
                st.session_state.campos_dinamicos = json.loads(op_para_editar['info_adicionais_ficha'])
                st.session_state.layout_confirmado = True

    st.header("✏️ Editar Ordem de Produção" if edit_mode else "➕ Lançar Nova OP")

    with sqlite3.connect('fabrica_master.db') as conn:
        conn.row_factory = sqlite3.Row
        maqs = pd.read_sql_query("SELECT nome FROM maquinas", conn)['nome'].tolist()
        sets = pd.read_sql_query("SELECT nome FROM setores", conn)['nome'].tolist()
        mods_df = pd.read_sql_query("SELECT * FROM modelos_op", conn)

    # --- PASSO 1: SELEÇÃO E LAYOUT (SÓ APARECE SE NÃO FOR EDIÇÃO) ---
    if not st.session_state.layout_confirmado:
        st.subheader("Passo 1: Seleção e Layout")
        # ... (seu código de seleção de máquina e atalhos permanece igual aqui)
        maq_sel = st.selectbox("Máquina Principal", [""] + maqs)
        # (Código dos atalhos e personalização omitido para brevidade, mantenha o que você já tem)
        if st.button("✅ CONFIRMAR E ABRIR FORMULÁRIO"):
            if maq_sel:
                st.session_state.layout_confirmado, st.session_state.maq_atual = True, maq_sel
                st.rerun()

    # --- PASSO 2: FORMULÁRIO DE REGISTRO / EDIÇÃO ---
    else:
        # Se for edição, buscamos os valores atuais para preencher os campos
        val = {}
        if edit_mode:
            with sqlite3.connect('fabrica_master.db') as conn:
                conn.row_factory = sqlite3.Row
                val = conn.execute("SELECT * FROM ordens WHERE id=?", (st.session_state.edit_op_id,)).fetchone()

        st.subheader(f"Passo 2: {'Ajustar Dados' if edit_mode else 'Registro'} - {st.session_state.maq_atual}")

        if edit_mode:
            if st.button("❌ Cancelar Edição"):
                st.session_state.edit_op_id = None
                st.session_state.layout_confirmado = False
                st.rerun()

        with st.form("f_completo"):
            g1, g2, g3 = st.columns(3)
            f_op = g1.text_input("Número OP", value=val['numero_op'] if edit_mode else "")
            f_cli = g2.text_input("Cliente", value=val['cliente'] if edit_mode else "")
            f_cnpj = g3.text_input("CNPJ", value=val['cnpj'] if edit_mode else "")

            # --- CORREÇÃO DAS DATAS ---
            # Se for edição, converte a string do banco para data. Se não, usa hoje.
            d_em_default = datetime.strptime(val['data_op'], '%Y-%m-%d').date() if edit_mode else date.today()
            d_en_default = datetime.strptime(val['data_entrega'], '%Y-%m-%d').date() if edit_mode else date.today()

            f_em = st.date_input("Emissão", d_em_default)
            f_en = st.date_input("Entrega (Nova Data)", d_en_default)  # Aqui você consegue mudar a data!

            st.write("### 🛠️ Especificações")
            cd = st.columns(3)
            for i, l in enumerate(st.session_state.campos_dinamicos.keys()):
                # Mantém os valores técnicos que já estavam na OP
                st.session_state.campos_dinamicos[l] = cd[i % 3].text_input(l,
                                                                            value=st.session_state.campos_dinamicos[l])

            st.write("### 🚛 Logística e Esteira")
            e1, e2, e3 = st.columns(3)
            emat = e1.text_input("Material Esteira", value=val['est_material'] if edit_mode else "")
            ealt = e1.text_input("Altura", value=val['est_altura'] if edit_mode else "")
            ecom = e2.text_input("Comprimento", value=val['est_comprimento'] if edit_mode else "")
            elar = e2.text_input("Largura", value=val['est_largura'] if edit_mode else "")
            epla = e3.text_input("Plataforma", value=val['est_plataforma'] if edit_mode else "")

            st.write("### 🏢 Distribuição")
            dist1, dist2, dist3 = st.columns(3)
            dv = dist1.text_input("Vendedor", value=val['dist_vendedor'] if edit_mode else "")
            dr = dist1.text_input("Revisor", value=val['dist_revisor'] if edit_mode else "")
            dp = dist2.text_input("PCP", value=val['dist_pcp'] if edit_mode else "")
            dj = dist2.text_input("Projeto", value=val['dist_projeto'] if edit_mode else "")
            de = dist3.text_input("Elétrica", value=val['dist_eletrica'] if edit_mode else "")
            dm = dist3.text_input("Montagem", value=val['dist_montagem'] if edit_mode else "")

            idx_lid = sets.index(val['responsavel_setor']) if edit_mode and val['responsavel_setor'] in sets else 0
            flid = st.selectbox("Líder Responsável", sets, index=idx_lid)

            fend = st.text_input("Endereço de Entrega", value=val['exp_endereco'] if edit_mode else "")
            fast = st.text_area("Assistência", value=val['ast_instalacao'] if edit_mode else "")

            # Botão Salvar (faz Update se for edição, ou Insert se for nova)
            if st.form_submit_button("ATUALIZAR OP" if edit_mode else "SALVAR OP"):
                with sqlite3.connect('fabrica_master.db') as conn:
                    if edit_mode:
                        conn.execute("""UPDATE ordens SET 
                            numero_op=?, equipamento=?, cliente=?, cnpj=?, data_op=?, data_entrega=?, responsavel_setor=?, 
                            est_material=?, est_altura=?, est_comprimento=?, est_largura=?, est_plataforma=?, 
                            dist_vendedor=?, dist_revisor=?, dist_pcp=?, dist_projeto=?, dist_eletrica=?, dist_montagem=?, 
                            exp_endereco=?, ast_instalacao=?, info_adicionais_ficha=? 
                            WHERE id=?""",
                                     (f_op, st.session_state.maq_atual, f_cli, f_cnpj, str(f_em), str(f_en), flid, emat,
                                      ealt, ecom,
                                      elar, epla, dv, dr, dp, dj, de, dm, fend, fast,
                                      json.dumps(st.session_state.campos_dinamicos), st.session_state.edit_op_id))
                        st.session_state.edit_op_id = None  # Limpa o modo edição após salvar
                    else:
                        conn.execute("""INSERT INTO ordens (
                            numero_op, equipamento, cliente, cnpj, data_op, data_entrega, responsavel_setor, 
                            est_material, est_altura, est_comprimento, est_largura, est_plataforma, 
                            dist_vendedor, dist_revisor, dist_pcp, dist_projeto, dist_eletrica, dist_montagem, 
                            exp_endereco, ast_instalacao, info_adicionais_ficha) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                     (f_op, st.session_state.maq_atual, f_cli, f_cnpj, str(f_em), str(f_en), flid, emat,
                                      ealt, ecom,
                                      elar, epla, dv, dr, dp, dj, de, dm, fend, fast,
                                      json.dumps(st.session_state.campos_dinamicos)))

                st.session_state.layout_confirmado = False
                st.success("Operação realizada com sucesso!")
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
        ops = conn.execute("SELECT * FROM ordens ORDER BY id DESC").fetchall()
        cargos_chat = [c[0] for c in conn.execute("SELECT DISTINCT cargo FROM usuarios WHERE ativo=1").fetchall()]

    for op in ops:
        # Lógica de cores por prazo
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

        with st.expander(f"{cor_alerta} OP {op['numero_op']} - {op['cliente']} | Entrega em: {op['data_entrega']}"):
            t1, t2, t3 = st.tabs(["Ficha Técnica", "Checklist", "Acompanhamento"])

            with t1:
                # --- 1. ALERTAS DE PRAZO ---
                if cor_alerta == "🔴":
                    st.error(f"🚨 **URGENTE:** Entrega em {dias_restantes} dias!")
                elif cor_alerta == "🟡":
                    st.warning(f"⚠️ **ATENÇÃO:** Entrega em {dias_restantes} dias.")

                # --- 2. INFORMAÇÕES GERAIS ---
                st.subheader("📄 Dados do Projeto")
                c_g1, c_g2, c_g3 = st.columns(3)
                c_g1.write(f"**Nº OP:** {op['numero_op']}")
                c_g1.write(f"**Cliente:** {op['cliente']}")
                c_g2.write(f"**Equipamento:** {op['equipamento']}")
                c_g2.write(f"**CNPJ:** {op['cnpj']}")
                c_g3.write(f"**Emissão:** {op['data_op']}")
                c_g3.write(f"**Entrega:** {op['data_entrega']}")

                st.divider()

                # --- 3. ESPECIFICAÇÕES TÉCNICAS (DINÂMICAS) ---
                st.subheader("🛠️ Especificações Técnicas")
                specs = json.loads(op['info_adicionais_ficha'])
                cols_specs = st.columns(3)
                for i, (campo, valor) in enumerate(specs.items()):
                    cols_specs[i % 3].write(f"**{campo}:** {valor}")

                st.divider()

                # --- 4. LOGÍSTICA E DISTRIBUIÇÃO ---
                st.subheader("🚛 Logística e Distribuição")
                l1, l2, l3 = st.columns(3)
                l1.write(f"**Material:** {op['est_material']}")
                l1.write(f"**Altura:** {op['est_altura']}")
                l2.write(f"**Comprimento:** {op['est_comprimento']}")
                l2.write(f"**Largura:** {op['est_largura']}")
                l3.write(f"**Plataforma:** {op['est_plataforma']}")
                l3.write(f"**Líder:** {op['responsavel_setor']}")

                st.write(f"**📍 Endereço de Entrega:** {op['exp_endereco']}")

                d1, d2, d3 = st.columns(3)
                d1.write(f"**Vendedor:** {op['dist_vendedor']}")
                d1.write(f"**PCP:** {op['dist_pcp']}")
                d2.write(f"**Revisor:** {op['dist_revisor']}")
                d2.write(f"**Projeto:** {op['dist_projeto']}")
                d3.write(f"**Elétrica:** {op['dist_eletrica']}")
                d3.write(f"**Montagem:** {op['dist_montagem']}")
                st.write(f"**🔧 Assistência:** {op['ast_instalacao']}")

                st.divider()

                # --- 5. GESTÃO DE ANEXOS ---
                st.subheader("📁 Anexos e Fotos")
                if op['anexo']:
                    caminho_arq = os.path.join("anexos", op['anexo'])
                    if os.path.exists(caminho_arq):
                        ext = op['anexo'].split(".")[-1].lower()
                        if ext in ["png", "jpg", "jpeg"]:
                            st.image(caminho_arq, caption="Preview do Anexo", width=300)

                        c_arq1, c_arq2 = st.columns(2)
                        with open(caminho_arq, "rb") as f:
                            c_arq1.download_button("📥 Baixar Anexo", f, file_name=op['anexo'], key=f"dl_{op['id']}")
                        if c_arq2.button("🗑️ Remover", key=f"rm_{op['id']}"):
                            with sqlite3.connect('fabrica_master.db') as conn:
                                conn.execute("UPDATE ordens SET anexo=NULL WHERE id=?", (op['id'],))
                            os.remove(caminho_arq)
                            st.rerun()

                arquivo_upload = st.file_uploader("Novo Anexo (Foto/PDF)", type=["pdf", "png", "jpg", "jpeg"],
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

                # --- 6. BOTÕES DE AÇÃO ---
                c_pdf, c_edit = st.columns(2)
                c_pdf.download_button("📂 Gerar PDF Completo", gerar_pdf_op(op), f"OP_{op['numero_op']}.pdf",
                                      key=f"pdf_btn_{op['id']}")
                if c_edit.button("✏️ Editar Ordem", key=f"edit_btn_{op['id']}"):
                    # ESTA É A ALTERAÇÃO: Preparamos a memória antes de mudar de página
                    st.session_state.edit_op_id = op['id']
                    st.session_state.maq_atual = op['equipamento']
                    st.session_state.campos_dinamicos = json.loads(op['info_adicionais_ficha'])
                    st.session_state.layout_confirmado = True

                    # Opcional: Avisar o usuário ou apenas dar o rerun
                    st.rerun()

            with t2:
                with sqlite3.connect('fabrica_master.db') as conn:
                    m = conn.execute("SELECT conjuntos FROM maquinas WHERE nome=?", (op['equipamento'],)).fetchone()
                it = [i.strip() for i in m[0].split(",")] if m else []
                done = op['checks_concluidos'].split("|") if op['checks_concluidos'] else []
                sel = [i for i in it if st.checkbox(i, i in done, key=f"ck_{op['id']}_{i}")]
                if st.button("Salvar Checklist", key=f"sck_{op['id']}"):
                    p = int((len(sel) / len(it)) * 100) if it else 0
                    with sqlite3.connect('fabrica_master.db') as conn:
                        conn.execute("UPDATE ordens SET progresso=?, checks_concluidos=? WHERE id=?",
                                     (p, "|".join(sel), op['id']))
                    st.rerun()

            with t3:
                logs = json.loads(op['acompanhamento_log'])
                with st.form(f"chat_{op['id']}"):
                    dst = st.selectbox("Para", cargos_chat)
                    msg = st.text_area("Mensagem")
                    if st.form_submit_button("Enviar"):
                        logs.append({"cargo_destino": dst, "user_origem": st.session_state.user_logado,
                                     "data_inicio": datetime.now().strftime("%d/%m %H:%M"), "msg": msg, "resposta": "",
                                     "status": "Pendente", "historico_conversa": []})
                        with sqlite3.connect('fabrica_master.db') as conn:
                            conn.execute("UPDATE ordens SET acompanhamento_log=? WHERE id=?",
                                         (json.dumps(logs), op['id']))
                        st.rerun()
                # Exibição dos logs conforme seu código original...
                for i, l in enumerate(reversed(logs)):
                    st.info(f"💬 De: {l['user_origem']} - {l['msg']}")  # Resumo para brevidade



# --- RELATÓRIO DINÂMICO COM GRÁFICO POR LÍDER ---
elif menu == "📊 Relatório":
    st.header("📊 Painel de Controle de Produção")

    with sqlite3.connect('fabrica_master.db') as conn:
        # Mantendo o seu critério: Somente o que está em andamento (1% a 99%)
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
        # --- SEÇÃO 1: GRÁFICO DE PIZZA ---
        st.subheader("👥 Distribuição de OPs por Líder")

        # Agrupamento para o gráfico
        df_pizza = df['Líder'].value_counts().reset_index()
        df_pizza.columns = ['Líder', 'Qtd OPs']

        import plotly.express as px

        fig = px.pie(
            df_pizza,
            values='Qtd OPs',
            names='Líder',
            hole=0.4,  # Estilo rosca/donut
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # --- SEÇÃO 2: TABELA DETALHADA ---
        st.subheader("📋 Detalhamento de OPs em Fluxo")
        st.dataframe(
            df,
            column_config={
                "Progresso %": st.column_config.ProgressColumn(
                    "Status",
                    format="%d%%",
                    min_value=0,
                    max_value=100,
                ),
            },
            hide_index=True,
            use_container_width=True
        )

        # Métricas de Resumo
        c1, c2, c3 = st.columns(3)
        c1.metric("OPs em Produção", len(df))
        c2.metric("Líderes Ativos", df['Líder'].nunique())
        c3.info("Filtro: Progresso entre 1% e 99%")

    else:
        st.info("Nenhuma OP em andamento (1% a 99%) para exibir no gráfico.")

    # --- HISTÓRICO (OPCIONAL) ---
    with st.expander("🔍 Ver todas as OPs (Histórico 0% e 100%)"):
        with sqlite3.connect('fabrica_master.db') as conn:
            df_total = pd.read_sql_query("SELECT numero_op, cliente, responsavel_setor, progresso FROM ordens", conn)
            st.write(df_total)


"""
streamlit run teste1.py
"""