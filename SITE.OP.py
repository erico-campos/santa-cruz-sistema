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
# --- LÓGICA DE ACESSO CONFORME CARGO E NÍVEL ---
with st.sidebar:
    st.title("Santa Cruz Nav")

    # Lógica de permissões baseada no seu pedido:
    cargo = str(st.session_state.cargo_logado).upper()
    nivel = st.session_state.nivel

    opcoes = ["📋 Lista de OPs"]  # Padrão para todos

    # Regra: ADM ou PCP (qualquer um que contenha PCP ou ADM no cargo)
    if "ADM" in cargo or "PCP" in cargo or nivel == "ADM":
        opcoes = ["📊 Relatório", "📋 Lista de OPs", "➕ Nova OP", "⚙️ Configurações"]

    # Regra: Líder ou Vendas
    elif nivel in ["LIDER", "VENDAS"]:
        opcoes = ["📋 Lista de OPs", "📊 Relatório", "➕ Nova OP"]

    # Regra: Usuário comum
    else:
        opcoes = ["📋 Lista de OPs", "➕ Nova OP"]

    menu = st.radio("Ir para:", opcoes)

    st.divider()
    st.write(f"👤 {st.session_state.user_logado}")
    st.write(f"🛠️ {cargo}")


# --- PÁGINA DE CONFIGURAÇÕES (LIBERDADE TOTAL E GESTÃO) ---
if menu == "⚙️ Configurações":
    st.title("⚙️ Gestão de Fábrica - Santa Cruz")

    tab_u, tab_m = st.tabs(["👤 Usuários e Líderes", "🚜 Máquinas e Periféricos"])

    # --- GESTÃO DE USUÁRIOS, LÍDERES, ADM, PCP ---
    with tab_u:
        st.subheader("📝 Cadastro de Pessoas")

        try:
            df_u = conn_sheets.read(worksheet="USUARIOS", ttl=0)
        except:
            df_u = pd.DataFrame(columns=["usuario", "senha", "nome", "nivel", "cargo", "ativo"])

        with st.expander("➕ Adicionar/Editar Usuário ou Líder"):
            with st.form("form_pessoal", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    u_id = st.text_input("ID/Login (Ex: pcp02, lider_laser)")
                    u_nome = st.text_input("Nome Completo")
                    u_cargo = st.text_input("Cargo ou Setor (Ex: Líder de Montagem, PCP, ADM)")
                with col2:
                    u_senha = st.text_input("Senha", type="password")
                    # Níveis conforme sua regra
                    u_nivel = st.selectbox("Nível de Acesso", ["USER", "LIDER", "ADM", "VENDAS"])
                    u_ativo = st.checkbox("Usuário Ativo", value=True)

                if st.form_submit_button("💾 Salvar Registro"):
                    if u_id and u_senha:
                        # Remove anterior para atualizar
                        df_u = df_u[df_u['usuario'] != u_id]
                        novo_u = pd.DataFrame([{
                            "usuario": u_id, "senha": u_senha, "nome": u_nome,
                            "nivel": u_nivel, "cargo": u_cargo, "ativo": 1 if u_ativo else 0
                        }])
                        df_final_u = pd.concat([df_u, novo_u], ignore_index=True)
                        conn_sheets.update(worksheet="USUARIOS", data=df_final_u)
                        st.success(f"Registro de {u_id} salvo com sucesso!")
                        st.rerun()

        # Tabela de Edição/Exclusão
        st.write("---")
        for i, row in df_u.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            status = "✅" if row['ativo'] == 1 else "🚫"
            c1.write(f"{status} **{row['nome']}** | {row['cargo']} ({row['nivel']})")
            if c3.button("🗑️ Apagar", key=f"del_u_{row['usuario']}"):
                df_u = df_u[df_u['usuario'] != row['usuario']]
                conn_sheets.update(worksheet="USUARIOS", data=df_u)
                st.rerun()

    # --- GESTÃO DE MÁQUINAS E PERIFÉRICOS ---
    with tab_m:
        st.subheader("🚜 Máquinas e Componentes")
        try:
            df_m = conn_sheets.read(worksheet="MAQUINAS", ttl=0)
        except:
            df_m = pd.DataFrame(columns=["nome_maquina", "perifericos"])

        with st.form("form_maq"):
            m_nome = st.text_input("Nome da Máquina")
            m_peri = st.text_area("Periféricos / Peças desta Máquina (separe por vírgula)")
            if st.form_submit_button("💾 Salvar Máquina"):
                df_m = df_m[df_m['nome_maquina'] != m_nome]
                novo_m = pd.DataFrame([{"nome_maquina": m_nome.upper(), "perifericos": m_peri}])
                conn_sheets.update(worksheet="MAQUINAS", data=pd.concat([df_m, novo_m], ignore_index=True))
                st.rerun()

        st.write("---")
        for i, row in df_m.iterrows():
            c_m1, c_m2 = st.columns([4, 1])
            c_m1.write(f"🚜 **{row['nome_maquina']}**: {row['perifericos']}")
            if c_m2.button("🗑️", key=f"del_m_{row['nome_maquina']}"):
                df_m = df_m[df_m['nome_maquina'] != row['nome_maquina']]
                conn_sheets.update(worksheet="MAQUINAS", data=df_m)
                st.rerun()

# --- Nova Op ---
# --- PÁGINA: NOVA OP ---
if menu == "➕ Nova OP":
    st.title("➕ Abrir Nova Ordem de Produção")

    # 1. Busca lista de máquinas cadastradas
    try:
        df_maquinas = conn_sheets.read(worksheet="MAQUINAS", ttl=0)
        lista_maquinas = df_maquinas['nome_maquina'].tolist()
    except:
        lista_maquinas = ["Cadastre uma máquina primeiro"]

    with st.form("form_nova_op", clear_on_submit=True):
        st.subheader("Informações do Cliente")
        c1, c2 = st.columns(2)
        n_op = c1.text_input("Número da OP")
        cliente = c2.text_input("Nome do Cliente")

        st.divider()
        st.subheader("Configuração Técnica")

        col_m, col_d = st.columns([1, 1])
        maquina_sel = col_m.selectbox("Selecione a Máquina", lista_maquinas)

        # Busca periféricos da máquina selecionada para sugestão
        perifericos_sugeridos = ""
        if maquina_sel in lista_maquinas:
            perifericos_sugeridos = df_maquinas[df_maquinas['nome_maquina'] == maquina_sel]['perifericos'].values[0]

        pecas = st.text_area("Descrição das Peças / Periféricos", value=perifericos_sugeridos)

        st.divider()
        st.subheader("Prazos e Responsáveis")
        c3, c4 = st.columns(2)
        data_ent = c3.date_input("Data Prevista de Entrega")
        vendedor = c4.text_input("Vendedor Responsável")

        btn_gerar = st.form_submit_button("🚀 Gerar Ordem de Produção")

        if btn_gerar:
            if n_op and cliente:
                try:
                    # Lê dados atuais
                    df_dados = conn_sheets.read(worksheet="DADOS", ttl=0)

                    # Cria nova linha respeitando suas colunas da planilha
                    nova_linha = pd.DataFrame([{
                        "numero_op": n_op,
                        "cliente": cliente,
                        "data_op": pd.Timestamp.now().strftime('%d/%m/%Y'),
                        "data_entrega": data_ent.strftime('%d/%m/%Y'),
                        "vendedor": vendedor,
                        "equipamento": maquina_sel,
                        "info_adicionais_ficha": pecas,
                        "status": "Pendente",
                        "responsavel_setor": st.session_state.user_logado,  # Quem criou
                        "progresso": 0,
                        "checks_concluidos": ""
                    }])

                    # Atualiza Planilha
                    df_final = pd.concat([df_dados, nova_linha], ignore_index=True)
                    conn_sheets.update(worksheet="DADOS", data=df_final)

                    st.success(f"✅ OP {n_op} para {cliente} gerada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar OP: {e}")
            else:
                st.warning("Preencha o Número da OP e o Cliente.")

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

# --- PÁGINA: LISTA DE OPs ---
if menu == "📋 Lista de OPs":
    st.title("📋 Lista de Ordens de Produção")

    try:
        # 1. Leitura dos dados da planilha
        df = conn_sheets.read(ttl=0)

        if df.empty:
            st.info("Nenhuma ordem de produção encontrada.")
        else:
            # --- LÓGICA DE FILTRO DE ACESSO ---
            cargo_user = str(st.session_state.cargo_logado).upper()
            nivel_user = st.session_state.nivel
            nome_user = st.session_state.user_logado

            # Se for LIDER ou VENDAS, filtra para ver apenas o que é DELE
            if nivel_user in ["LIDER", "VENDAS"] and "ADM" not in cargo_user and "PCP" not in cargo_user:
                # Filtra pela coluna de quem criou a OP (ajuste o nome da coluna se necessário, ex: 'SOLICITANTE')
                if 'SOLICITANTE' in df.columns:
                    df = df[df['SOLICITANTE'] == nome_user]
                st.warning(f"Exibindo apenas OPs criadas por: {nome_user}")

            # --- FILTROS DE PESQUISA NA TELA ---
            col_f1, col_f2 = st.columns(2)
            busca_op = col_f1.text_input("🔍 Buscar por Número da OP ou Cliente")

            status_opcoes = ["Todos"] + list(df['STATUS'].unique()) if 'STATUS' in df.columns else ["Todos"]
            filtro_status = col_f2.selectbox("Filtrar por Status", status_opcoes)

            # Aplica filtros de pesquisa
            if busca_op:
                df = df[df.astype(str).apply(lambda x: busca_op.lower() in x.str.lower().values, axis=1)]
            if filtro_status != "Todos":
                df = df[df['STATUS'] == filtro_status]

            # --- EXIBIÇÃO DAS OPs EM CARDS ---
            st.write(f"Exibindo **{len(df)}** resultados:")

            for i, row in df.iterrows():
                with st.expander(f"📦 OP: {row.get('OP', 'N/A')} - Cliente: {row.get('CLIENTE', 'N/A')}"):
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"**Data:** {row.get('DATA', 'N/A')}")
                    c2.markdown(f"**Máquina:** {row.get('MAQUINA', 'N/A')}")

                    # Cor do Status
                    status_atual = row.get('STATUS', 'Pendente')
                    cor = "🔴" if status_atual == "Pendente" else "🟡" if status_atual == "Em Produção" else "🟢"
                    c3.markdown(f"**Status:** {cor} {status_atual}")

                    st.divider()
                    st.write(f"**Peças/Descrição:** {row.get('PEÇAS', 'N/A')}")

                    # Botão para Ver Detalhes / Editar (Apenas ADM/PCP/LIDER podem editar)
                    if nivel_user in ["ADM", "PCP", "LIDER"]:
                        if st.button(f"📝 Editar OP {row.get('OP')}", key=f"edit_{i}"):
                            st.session_state.op_para_editar = row.get('OP')
                            st.info("Funcionalidade de edição selecionada.")

    except Exception as e:
        st.error(f"Erro ao carregar lista: {e}")
        st.info("Verifique se a aba 'DADOS' é a primeira da sua planilha.")

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
















