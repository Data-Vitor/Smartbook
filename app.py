"""
SMARTBOOK | app.py
Interface. NENHUM SQL aqui: tudo que fala com o banco esta em src/db.py.

Rodar:  streamlit run app.py

PRIVACIDADE: a base desta demonstracao e 100% sintetica. Nenhum dado
real de hospede em nenhum ponto do sistema.
"""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import db  # noqa: E402


st.set_page_config(page_title="Smartbook", page_icon="📦", layout="centered")


# =====================================================================
# ESTILO
# Streamlit nao tem barra fixa no rodape (o layout e fluxo de documento,
# empilhado de cima para baixo), entao a navegacao dos mockups virou
# menu lateral. No celular ele abre pelo icone de menu.
# =====================================================================
st.markdown("""
<style>
  .bloco-cartao { padding-top: .2rem; }
  .linha-ticket { font-size: 1.35rem; font-weight: 700; letter-spacing: .5px; }
  .linha-quarto { font-size: .95rem; color: #555; }
  .linha-nome   { font-size: 1.05rem; font-weight: 600; margin-top: .15rem; }
  .linha-data   { font-size: .85rem; color: #666; }
  .linha-desc   { font-size: .92rem; color: #333; margin-top: .25rem; }
  .selo         { display:inline-block; padding:.1rem .45rem; border-radius:.35rem;
                  font-size:.72rem; font-weight:700; margin-left:.4rem; }
  .selo-alerta  { background:#FFF0C2; color:#7A5A00; }
  .selo-vencido { background:#FFD9D9; color:#8B1E1E; }
  .selo-trip    { background:#E2ECFF; color:#1F3D7A; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# CONEXAO
# cache_resource mantem UMA conexao viva entre reruns. Sem isso, cada
# clique abriria um sqlite3.connect novo.
# =====================================================================
@st.cache_resource
def conexao():
    return db.conectar()


conn = conexao()


# =====================================================================
# HELPERS DE TELA
# =====================================================================
def formatar_data(iso):
    d = datetime.strptime(iso, "%Y-%m-%d %H:%M:%S")
    return d.strftime("%d/%m/%Y %H:%M")


def tempo_no_armario(dias, horas):
    if dias >= 1:
        return f"há {dias} dia" + ("s" if dias > 1 else "")
    return f"há {int(horas)}h"


def selo(texto, classe):
    return f'<span class="selo {classe}">{texto}</span>'


def cartao(p):
    """Um protocolo na lista.

    Ordem das informacoes: TICKET primeiro. Ele e o que o colaborador
    precisa para achar o item no armario, entao e a linha mais visivel.
    Depois quarto e nome, que sao o que confere a identidade.
    """
    with st.container(border=True):
        col_foto, col_texto = st.columns([1, 2.6], gap="medium")

        with col_foto:
            caminho = db.foto_item(conn, p["id"])
            if caminho:
                st.image(str(caminho), use_container_width=True)
            else:
                st.caption("sem foto")

        with col_texto:
            selos = ""
            if p["situacao_descarte"] == "vencido":
                selos += selo("VENCIDO", "selo-vencido")
            elif p["situacao_descarte"] == "alerta":
                selos += selo("PERTO DO PRAZO", "selo-alerta")
            if p["hospede_tipo"] == "tripulante":
                selos += selo(p["companhia"] or "TRIPULACAO", "selo-trip")

            st.markdown(f"""
<div class="bloco-cartao">
  <span class="linha-ticket">🎫 {p['ticket']}</span>
  <span class="linha-quarto">· Quarto {p['quarto']}</span>{selos}
  <div class="linha-nome">{p['hospede_nome']}</div>
  <div class="linha-data">{formatar_data(p['recebido_em'])} ·
      {tempo_no_armario(p['dias_permanencia'], p['horas_permanencia'])}</div>
  <div class="linha-desc">{p['categoria']} — {p['descricao']}</div>
</div>
""", unsafe_allow_html=True)

            with st.expander("Detalhes"):
                st.write(f"**Código do sistema:** {p['codigo']}")
                st.write(f"**Recebido por:** {p['recebido_por']}")
                if p["hospede_tipo"] == "tripulante":
                    st.write(f"**Companhia:** {p['companhia']}")
                st.button("Registrar retirada", key=f"ret_{p['id']}",
                          disabled=True, help="Próxima etapa do projeto")


# =====================================================================
# NAVEGACAO
# =====================================================================
with st.sidebar:
    st.title("Smartbook")
    pagina = st.radio(
        "Ir para",
        ["Protocolos ativos", "Registrar", "Retirada", "Descarte", "Analytics"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Base de demonstração sintética. "
               "Nenhum dado real de hóspede.")


# =====================================================================
# PAGINA: PROTOCOLOS ATIVOS
# =====================================================================
if pagina == "Protocolos ativos":
    st.title("Smartbook")

    c = db.contadores(conn)
    m1, m2, m3 = st.columns(3)
    m1.metric("Protocolos ativos", c["ativos"])
    m2.metric("Perto do prazo", c["vencidos"],
              help="Mais de 150 dias no armário. Política de descarte: 180 dias.")
    m3.metric("Recebidos hoje", c["recebidos_hoje"])

    if c["colisoes"]:
        st.warning(f"{c['colisoes']} ticket(s) repetido(s) entre protocolos ativos. "
                   "Confira pela foto e pelo nome antes de entregar.")

    busca = st.text_input(
        "Buscar",
        placeholder="Ticket, quarto ou nome do hóspede",
        label_visibility="collapsed",
    )

    f1, f2 = st.columns(2)
    ordem = f1.selectbox("Ordenar por", list(db.ORDENS.keys()))
    periodo = f2.selectbox("Período", list(db.PERIODOS.keys()))

    st.button("＋ Novo protocolo", use_container_width=True,
              disabled=True, help="Próxima etapa do projeto")

    st.divider()

    LIMITE = 30
    itens = db.listar_ativos(conn, ordem, periodo, busca, limite=LIMITE)
    total = db.contar_ativos_filtrados(conn, periodo, busca)

    if not itens:
        if busca:
            st.info(f"Nenhum protocolo ativo para “{busca}”. "
                    "Tente o número do ticket, o quarto ou parte do nome.")
        else:
            st.info("Nenhum protocolo ativo neste período.")
    else:
        if total > LIMITE:
            st.caption(f"Mostrando {len(itens)} de {total}. "
                       "Use a busca para chegar mais perto.")
        else:
            st.caption(f"{total} protocolo(s)")
        for p in itens:
            cartao(p)

else:
    st.title(pagina)
    st.info("Etapa seguinte do projeto. A tela de protocolos ativos já está funcional.")
