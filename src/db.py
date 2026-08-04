"""
SMARTBOOK | db.py
Camada de acesso ao banco. NENHUM import de streamlit aqui.

Essa separacao existe para duas coisas:
  1. as consultas podem ser testadas sem abrir o app
  2. trocar a interface depois nao exige reescrever a logica

Regra: nenhuma funcao daqui devolve HTML ou componente de tela. Só dado.
"""

import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "smartbook.db"


# =====================================================================
# CONEXAO
# =====================================================================
def conectar():
    """Abre conexao com row_factory: o resultado vira dict, nao tupla.

    Sem isso, cada consulta devolveria ('SB-2025-0001', 'Vitor', ...) e
    a tela teria que acessar por posicao (linha[0], linha[1]). Com dict,
    acessa por nome (linha['codigo']), que nao quebra se a query mudar
    de ordem.
    """
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _linhas(cur):
    return [dict(r) for r in cur.fetchall()]


# =====================================================================
# CONTADORES
# =====================================================================
def contadores(conn):
    """Numeros do topo da tela, em uma consulta so.

    Uma query com tres SELECT aninhados custa menos que tres idas ao
    banco, e mantem os numeros consistentes entre si (nao ha risco de
    um item ser retirado entre a primeira e a terceira consulta).
    """
    sql = """
        SELECT
          (SELECT COUNT(*) FROM vw_protocolo WHERE status = 'ativo')      AS ativos,
          (SELECT COUNT(*) FROM vw_protocolo_vencido)                     AS vencidos,
          (SELECT COUNT(*) FROM protocolo
            WHERE date(recebido_em) = date('now','localtime'))            AS recebidos_hoje,
          (SELECT COUNT(*) FROM vw_ticket_colidido)                       AS colisoes
    """
    return dict(conn.execute(sql).fetchone())


# =====================================================================
# LISTAGEM
# =====================================================================

# Whitelist de ordenacao. ORDER BY nao aceita parametro (?), entao o
# valor entra na string por concatenacao. Aceitar texto do usuario aqui
# seria porta aberta para SQL injection: o dicionario garante que so
# expressoes escritas por nos cheguem na consulta.
ORDENS = {
    "Mais recentes":  "recebido_em DESC",
    "Mais antigos":   "recebido_em ASC",
    "Nome (A-Z)":     "hospede_nome ASC",
    "Quarto":         "CAST(quarto AS INTEGER) ASC",
    "Ticket":         "CAST(ticket AS INTEGER) ASC",
}

PERIODOS = {
    "Sempre":        None,
    "Últimas 24h":   "-1 day",
    "Últimos 7 dias": "-7 days",
    "Últimos 30 dias": "-30 days",
}


def listar_ativos(conn, ordem="Mais recentes", periodo="Sempre", busca="", limite=50):
    """Protocolos ativos, com filtro de periodo, ordenacao e busca.

    'busca' e um campo unico de proposito: no balcao, obrigar a escolher
    entre buscar por ticket, nome ou quarto e fricção. A funcao decide
    sozinha o que fazer com o que foi digitado.
    """
    where = ["status = 'ativo'"]
    params = []

    if PERIODOS.get(periodo):
        where.append("recebido_em >= datetime('now','localtime',?)")
        params.append(PERIODOS[periodo])

    termo = busca.strip()
    if termo:
        if termo.isdigit():
            # numero pode ser ticket ou quarto; procura nos dois.
            # ticket_num compara sem zero a esquerda: '42' acha '0042'.
            where.append("(ticket_num = ? OR quarto = ?)")
            params += [int(termo), termo]
        else:
            where.append("hospede_nome LIKE ?")
            params.append(f"%{termo}%")

    sql = f"""
        SELECT id, codigo, ticket, hospede_nome, hospede_tipo, companhia,
               quarto, categoria, descricao, recebido_em, recebido_por,
               dias_permanencia, horas_permanencia, situacao_descarte
        FROM vw_protocolo
        WHERE {' AND '.join(where)}
        ORDER BY {ORDENS.get(ordem, ORDENS['Mais recentes'])}
        LIMIT ?
    """
    return _linhas(conn.execute(sql, params + [limite]))


def contar_ativos_filtrados(conn, periodo="Sempre", busca=""):
    """Quantos resultados o filtro atual tem, ignorando o LIMIT.

    Necessario para a tela poder avisar 'mostrando 50 de 132'.
    """
    where = ["status = 'ativo'"]
    params = []

    if PERIODOS.get(periodo):
        where.append("recebido_em >= datetime('now','localtime',?)")
        params.append(PERIODOS[periodo])

    termo = busca.strip()
    if termo:
        if termo.isdigit():
            where.append("(ticket_num = ? OR quarto = ?)")
            params += [int(termo), termo]
        else:
            where.append("hospede_nome LIKE ?")
            params.append(f"%{termo}%")

    sql = f"SELECT COUNT(*) AS n FROM vw_protocolo WHERE {' AND '.join(where)}"
    return conn.execute(sql, params).fetchone()["n"]


# =====================================================================
# DETALHE
# =====================================================================
def protocolo(conn, protocolo_id):
    cur = conn.execute("SELECT * FROM vw_protocolo WHERE id = ?", (protocolo_id,))
    linha = cur.fetchone()
    return dict(linha) if linha else None


def anexos(conn, protocolo_id, tipo=None):
    sql = "SELECT tipo, arquivo_path FROM anexo WHERE protocolo_id = ?"
    params = [protocolo_id]
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    return _linhas(conn.execute(sql, params))


def foto_item(conn, protocolo_id):
    """Caminho ABSOLUTO da foto, ou None. O banco guarda relativo."""
    r = anexos(conn, protocolo_id, "item")
    if not r:
        return None
    caminho = RAIZ / r[0]["arquivo_path"]
    return caminho if caminho.exists() else None


# =====================================================================
# TICKET
# =====================================================================
def ticket_em_uso(conn, ticket):
    """Protocolos ATIVOS que ja usam este ticket.

    Só ativos importam: ticket repetido entre um item entregue ano
    passado e um que chegou hoje nao e problema, porque o antigo nao
    esta mais no armario.

    Usado no registro para AVISAR, nunca para bloquear. Ver o comentario
    da coluna ticket no schema.sql.
    """
    sql = """
        SELECT id, codigo, ticket, hospede_nome, quarto, categoria, recebido_em
        FROM vw_protocolo
        WHERE status = 'ativo' AND ticket_num = CAST(? AS INTEGER)
    """
    return _linhas(conn.execute(sql, (ticket,)))


# =====================================================================
# ANALYTICS
# =====================================================================
def volume_por_turno(conn):
    return _linhas(conn.execute("SELECT * FROM vw_volume_turno"))


def vencidos(conn):
    return _linhas(conn.execute("SELECT * FROM vw_protocolo_vencido"))


def colisoes(conn):
    return _linhas(conn.execute("SELECT * FROM vw_ticket_colidido"))


# =====================================================================
# TESTE RAPIDO
#   python src/db.py
# Roda sem streamlit, de proposito: se quebrar aqui, o problema e de
# consulta, nao de tela.
# =====================================================================
if __name__ == "__main__":
    c = conectar()
    print("contadores:", contadores(c))
    print()
    for p in listar_ativos(c, limite=3):
        print(f"  {p['codigo']} | ticket {p['ticket']} | qto {p['quarto']} | "
              f"{p['hospede_nome']} | {p['categoria']}")
    print()
    print("busca por texto 'ana':", len(listar_ativos(c, busca="ana")), "resultado(s)")
    algum = listar_ativos(c, limite=1)[0]
    print(f"busca pelo ticket {algum['ticket']}:",
          len(listar_ativos(c, busca=algum['ticket'])), "resultado(s)")
    print(f"busca sem zero a esquerda ({algum['ticket'].lstrip('0')}):",
          len(listar_ativos(c, busca=algum['ticket'].lstrip('0'))), "resultado(s)")
    print("foto do primeiro:", foto_item(c, algum["id"]))
    c.close()
