"""
SMARTBOOK | seed.py
Gerador de base sintetica para demonstracao.

NENHUM DADO REAL DE HOSPEDE. Todos os nomes vem da biblioteca Faker.
Nomes de companhia aerea sao informacao publica; a distribuicao de
horario de pernoite de tripulacao e inventada, nao observada.

Uso:
    python src/seed.py
"""

import math
import random
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageFont

# =====================================================================
# PARAMETROS DO MODELO
#
# Cada numero abaixo esta rotulado pela origem. A distincao importa:
# estimativa apresentada como medicao seria desonestidade, e o valor
# deste gerador nao esta em os dados serem verdadeiros (sao sinteticos
# por design) e sim em o MODELO GERADOR ser defensavel.
#
#   [OBSERVADO]  regra ou fato verificavel da operacao
#   [ESTIMADO]   estimativa de quem trabalha na portaria, SEM contagem
#                sistematica. Fonte: ~3 anos de operacao, tendo rodado
#                todos os turnos. Nao e medicao.
#   [DERIVADO]   calculado a partir dos dois acima, com a conta a vista
# =====================================================================

SEMENTE = 42            # base reproduzivel: mesmo comando, mesmo resultado

# --- volume ---
PROTOCOLOS_POR_DIA = 3        # [ESTIMADO] 5 a 6 em dia cheio, ~3 na media
DIAS_HISTORICO = 240          # [DERIVADO] > 180 para a politica de descarte
                              #            aparecer na base
N_PROTOCOLOS = PROTOCOLOS_POR_DIA * DIAS_HISTORICO   # [DERIVADO] 720

RAZAO_BAGAGEM = 9             # [ESTIMADO] ~9 bagagens para cada protocolo
PCT_PROTOCOLO = 1 / (1 + RAZAO_BAGAGEM)              # [DERIVADO] 0.10
ITENS_POR_DIA = PROTOCOLOS_POR_DIA / PCT_PROTOCOLO   # [DERIVADO] 30/dia
                              # bagagem + protocolo, dividem o mesmo rolo

# --- retirada ---
MEDIANA_HORAS_HOSPEDE = 24.0  # [ESTIMADO] encomenda sai em ~1 dia
MEDIANA_HORAS_TRIPULANTE = 3.5  # [ESTIMADO] tripulacao retira no mesmo pernoite
PCT_TRIPULANTE = 0.22         # [ESTIMADO] fatia de itens de tripulacao
PCT_TERCEIRO = 0.18           # [ESTIMADO] retiradas feitas por terceiro

# --- itens que encalham ---
# [DERIVADO] O armario tem ~30 itens dentro da janela de 180 dias, dos
# quais ~4 sao do dia. Sobram ~26 encalhados. Com 3 entradas por dia e
# janela de 180 dias: 26 / (3 * 180) = 4.8% das entradas encalham.
ARMARIO_OBSERVADO = 30        # [ESTIMADO] itens na prateleira, contagem de olho
ARMARIO_DO_DIA = 4            # [DERIVADO] 3/dia com mediana de 24h
DIAS_POLITICA_DESCARTE = 180  # [OBSERVADO] politica do hotel, 6 meses
PCT_NUNCA_RETIRADO = (ARMARIO_OBSERVADO - ARMARIO_DO_DIA) / (
    PROTOCOLOS_POR_DIA * DIAS_POLITICA_DESCARTE)     # [DERIVADO] 0.048

# [OBSERVADO] A limpeza do armario nao acontece no prazo: a ultima foi
# ha mais de um ano. Por isso a maioria dos itens vencidos continua
# ATIVA na base, em vez de descartada. Isso e o retrato da operacao, nao
# um defeito do gerador.
PCT_VENCIDO_DESCARTADO = 0.60

# --- rolo de tickets ---
# [DERIVADO] 9999 numeros / 30 itens por dia = 333 dias por volta.
# A folga sobre a politica de 180 dias e o que torna a colisao de ticket
# impossivel QUANDO a limpeza acontece no prazo. Ver README.
CICLO_ROLO_DIAS = 9999 / ITENS_POR_DIA               # [DERIVADO] 333

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "smartbook.db"
DIR_FOTOS = RAIZ / "data" / "fotos"

fake = Faker("pt_BR")
Faker.seed(SEMENTE)
random.seed(SEMENTE)


# =====================================================================
# DOMINIO
# =====================================================================
COMPANHIAS = ["Sky Airline", "Copa Airlines", "Swiss", "Air Europa", "Qatar Airways"]

COLABORADORES = [
    ("Ana Beatriz Correia", "manha"),
    ("Rafael Nunes",        "manha"),
    ("Juliana Prado",       "manha"),
    ("Marcos Vinicius Sa",  "tarde"),
    ("Carolina Bastos",     "tarde"),
    ("Diego Ferraz",        "tarde"),
    ("Paulo Henrique Reis", "madrugada"),
    ("Tatiane Moraes",      "madrugada"),
    ("Eduardo Lima",        "madrugada"),
]

# peso relativo de chegada por hora do dia (indice = hora)
CURVA_HOSPEDE = [
    1, 1, 1, 1, 1, 2,      # 00-05 madrugada quase vazia
    4, 8, 12, 18, 30, 34,  # 06-11 abre o correio
    26, 30, 36, 38, 34, 28,  # 12-17 pico
    20, 16, 12, 8, 5, 3,   # 18-23 cai
]

CURVA_TRIPULANTE = [
    14, 16, 15, 12, 10, 8,  # 00-05 chegada de voo
    6, 4, 3, 2, 2, 2,       # 06-11
    2, 2, 3, 3, 4, 5,       # 12-17
    6, 8, 10, 12, 14, 15,   # 18-23 saida de voo
]

# (categoria, peso) para hospede e para tripulante
MIX_HOSPEDE = [
    ("Encomenda", 45), ("Sacola", 20), ("Envelope", 15),
    ("Documento", 8), ("Flores", 5), ("Bagagem", 4), ("Outro", 3),
]
MIX_TRIPULANTE = [
    ("Bagagem", 48), ("Envelope", 18), ("Encomenda", 14),
    ("Sacola", 12), ("Documento", 5), ("Outro", 3),
]

DESCRICOES = {
    "Encomenda": ["Caixa Correios media", "Pacote Mercado Livre", "Caixa Amazon pequena",
                  "Encomenda Shopee", "Caixa Sedex grande", "Pacote Jadlog"],
    "Sacola":    ["Sacola de farmacia", "Sacola de loja Shopping Internacional",
                  "Sacola com marmita", "Sacola de roupa lavanderia", "Sacola de mercado"],
    "Envelope":  ["Envelope pardo A4", "Envelope branco pequeno",
                  "Envelope com cartao", "Envelope de agencia de viagem"],
    "Documento": ["Contrato em pasta", "Passaporte devolvido pela agencia",
                  "Comprovante de reserva", "Documento corporativo lacrado"],
    "Flores":    ["Buque pequeno", "Arranjo em vaso", "Caixa de rosas"],
    "Bagagem":   ["Mala de bordo preta", "Mala grande prata", "Mochila de tripulacao",
                  "Mala rigida azul", "Bag de piloto"],
    "Outro":     ["Guarda-chuva esquecido", "Carregador de notebook",
                  "Caixa termica", "Item nao identificado"],
}

CORES_CATEGORIA = {
    "Encomenda": (196, 154, 108), "Sacola": (120, 148, 176),
    "Envelope":  (222, 214, 196), "Documento": (168, 172, 178),
    "Flores":    (198, 122, 140), "Bagagem": (86, 96, 112),
    "Outro":     (140, 140, 132),
}

DOCS = ["RG", "CNH", "Passaporte", "Outro"]


# =====================================================================
# HELPERS
# =====================================================================
def gerar_quartos():
    """Torre 1: unidades 01-16. Torre 2: unidades 17-40. Andares 1-10.
    Andar 10 e parcial: torre 1 vai ate 1006, torre 2 ate 1033."""
    quartos = []
    for andar in range(1, 11):
        t1_max = 6 if andar == 10 else 16
        for u in range(1, t1_max + 1):
            quartos.append(f"{andar}{u:02d}")
        t2_min, t2_max = 17, (33 if andar == 10 else 40)
        for u in range(t2_min, t2_max + 1):
            quartos.append(f"{andar}{u:02d}")
    return quartos


def sortear(pares):
    """Sorteia um item de lista [(valor, peso), ...]."""
    valores = [v for v, _ in pares]
    pesos = [p for _, p in pares]
    return random.choices(valores, weights=pesos, k=1)[0]


def sortear_hora(curva):
    return random.choices(range(24), weights=curva, k=1)[0]


def horas_ate_retirada(tipo):
    """Lognormal: maioria rapida, cauda longa de alguns dias.

    O parametro mu de uma lognormal e o log da MEDIANA, entao ln() das
    constantes estimadas entrega exatamente a mediana informada pela
    operacao. sigma controla o tamanho da cauda.
    """
    if tipo == "tripulante":
        h = random.lognormvariate(math.log(MEDIANA_HORAS_TRIPULANTE), 0.8)
        return min(max(h, 0.3), 72)
    h = random.lognormvariate(math.log(MEDIANA_HORAS_HOSPEDE), 1.1)
    return min(max(h, 0.5), 24 * 20)


def turno_de(hora):
    if 7 <= hora <= 14:
        return "manha"
    if 15 <= hora <= 22:
        return "tarde"
    return "madrugada"


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "_" for c in t).strip("_").lower()


def carregar_fonte(tamanho):
    for caminho in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def gerar_foto_item(protocolo_id, categoria, descricao):
    """Placeholder procedural. Nao e foto real, e nao pretende ser."""
    img = Image.new("RGB", (320, 240), CORES_CATEGORIA.get(categoria, (150, 150, 150)))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, 307, 227], outline=(255, 255, 255), width=2)
    d.text((24, 90), categoria.upper(), font=carregar_fonte(22), fill=(255, 255, 255))
    d.text((24, 124), descricao[:30], font=carregar_fonte(13), fill=(240, 240, 240))
    d.text((24, 196), f"SINTETICO #{protocolo_id:04d}", font=carregar_fonte(11),
           fill=(255, 255, 255))
    caminho = DIR_FOTOS / f"item_{protocolo_id:04d}.jpg"
    img.save(caminho, "JPEG", quality=65)
    return f"data/fotos/{caminho.name}"


def gerar_tickets(n):
    """Simula o rolo fisico de tickets, em ordem cronologica.

    O rolo anda de 1 em 1, mas a MAIOR PARTE dos numeros e consumida por
    bagagem, que nao entra neste banco. Por isso dois protocolos
    seguidos nao tem tickets seguidos: tem buracos.

    O buraco leva em conta DUAS coisas:
      1. a bagagem, que consome ~85% dos numeros
      2. o fato de esta base ser uma AMOSTRA (400 dos ~5400 protocolos
         que passariam pela portaria em 240 dias)

    Ignorar o item 2 encolhe o consumo do rolo em 13x e faz a colisao
    sumir do dataset, o que seria falso: no volume real o rolo de 9999
    da a volta a cada ~67 dias, bem antes dos 180 dias da politica.

    Quando o rolo acaba, volta ao inicio. E a volta do rolo que produz
    colisao, nao coincidencia.
    """
    protocolos_reais = ITENS_POR_DIA * PCT_PROTOCOLO * DIAS_HISTORICO
    fator_amostra = protocolos_reais / n
    buraco_medio = (1 / PCT_PROTOCOLO) * fator_amostra

    tickets = []
    fim_rolo = 9999
    atual = random.randint(1, 400)

    for _ in range(n):
        atual += int(random.uniform(0.4, 1.6) * buraco_medio)

        if atual > fim_rolo:             # rolo acabou, comeca outro
            atual = random.randint(1, 20)
            sorte = random.random()
            if sorte < 0.18:
                fim_rolo = random.randint(400, 900)   # lote curto
            elif sorte < 0.28:
                fim_rolo = 99999                      # rolo de 5 digitos
            else:
                fim_rolo = 9999

        largura = 5 if fim_rolo > 9999 else 4
        tickets.append(f"{atual:0{largura}d}")

    return tickets


def gerar_comprovante(protocolo_id, tipo):
    """Placeholder de documento e autorizacao de terceiro.

    De proposito NAO desenha numero de documento, nem falso. O projeto
    nao armazena documento por inteiro em lugar nenhum, e a imagem de
    demonstracao segue a mesma regra.
    """
    rotulos = {"documento": ("DOCUMENTO DE IDENTIDADE", (72, 84, 104)),
               "autorizacao": ("AUTORIZACAO DE RETIRADA", (96, 84, 64))}
    titulo, cor = rotulos[tipo]

    img = Image.new("RGB", (320, 200), cor)
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 309, 189], outline=(255, 255, 255), width=2)
    d.text((22, 40), titulo, font=carregar_fonte(15), fill=(255, 255, 255))
    for n in range(4):                       # linhas de texto borradas
        d.line([(22, 88 + n * 18), (random.randint(160, 285), 88 + n * 18)],
               fill=(255, 255, 255, 90), width=3)
    d.text((22, 166), f"PLACEHOLDER SINTETICO #{protocolo_id:04d}",
           font=carregar_fonte(10), fill=(235, 235, 235))

    prefixo = "doc" if tipo == "documento" else "autoriz"
    caminho = DIR_FOTOS / f"{prefixo}_{protocolo_id:04d}.jpg"
    img.save(caminho, "JPEG", quality=65)
    return f"data/fotos/{caminho.name}"


def gerar_assinatura(protocolo_id):
    """Rabisco procedural. Substitui o canvas do app na base de demo."""
    img = Image.new("RGB", (300, 100), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x, y = 20, 60
    pontos = [(x, y)]
    for _ in range(random.randint(5, 9)):
        x += random.randint(20, 45)
        y = 60 + random.randint(-28, 22)
        pontos.append((min(x, 285), y))
    d.line(pontos, fill=(28, 42, 96), width=2, joint="curve")
    caminho = DIR_FOTOS / f"assin_{protocolo_id:04d}.png"
    img.save(caminho, "PNG")
    return f"data/fotos/{caminho.name}"


# =====================================================================
# GERACAO
# =====================================================================
def popular(conn):
    cur = conn.cursor()

    cur.executemany("INSERT INTO colaborador (nome, turno_padrao) VALUES (?, ?)",
                    COLABORADORES)
    colab_por_turno = {}
    for cid, nome, turno in cur.execute(
            "SELECT id, nome, turno_padrao FROM colaborador"):
        colab_por_turno.setdefault(turno, []).append(cid)

    cat_id = {nome: cid for cid, nome in
              cur.execute("SELECT id, nome FROM categoria_item")}

    quartos = gerar_quartos()
    agora = datetime.now().replace(microsecond=0)
    inicio = agora - timedelta(days=DIAS_HISTORICO)

    # Fase 1: gera os registros SEM id e SEM ticket.
    # O id e o ticket so podem ser atribuidos depois de ordenar por data,
    # porque os dois seguem a ordem de chegada no balcao.
    registros = []

    for _ in range(N_PROTOCOLOS):
        eh_tripulante = random.random() < PCT_TRIPULANTE
        tipo = "tripulante" if eh_tripulante else "hospede"
        companhia = random.choice(COMPANHIAS) if eh_tripulante else None
        curva = CURVA_TRIPULANTE if eh_tripulante else CURVA_HOSPEDE
        mix = MIX_TRIPULANTE if eh_tripulante else MIX_HOSPEDE

        dia = inicio + timedelta(days=random.uniform(0, DIAS_HISTORICO))
        recebido = dia.replace(hour=sortear_hora(curva),
                               minute=random.randint(0, 59),
                               second=random.randint(0, 59))
        if recebido > agora:
            recebido = agora - timedelta(hours=random.uniform(0.5, 6))

        categoria = sortear(mix)
        descricao = random.choice(DESCRICOES[categoria])
        recebido_por = random.choice(colab_por_turno[turno_de(recebido.hour)])

        entregue = entregue_por = None
        descartado = descartado_por = None
        r_tipo = r_nome = r_doc_tipo = r_doc_final = None

        if random.random() >= PCT_NUNCA_RETIRADO:
            saida = recebido + timedelta(hours=horas_ate_retirada(tipo))
            if saida < agora:
                entregue = saida
                entregue_por = random.choice(colab_por_turno[turno_de(saida.hour)])
                por_terceiro = random.random() < PCT_TERCEIRO
                r_tipo = "terceiro" if por_terceiro else "destinatario"
                r_nome = fake.name() if por_terceiro else None
                if por_terceiro or random.random() < 0.6:
                    r_doc_tipo = random.choice(DOCS)
                    r_doc_final = f"{random.randint(0, 999):03d}"
        else:
            idade = (agora - recebido).days
            if idade >= DIAS_POLITICA_DESCARTE and random.random() < PCT_VENCIDO_DESCARTADO:
                descartado = recebido + timedelta(days=DIAS_POLITICA_DESCARTE,
                                                  hours=random.uniform(1, 60))
                if descartado < agora:
                    descartado_por = random.choice(colab_por_turno["manha"])
                else:
                    descartado = None

        registros.append(dict(
            hospede_nome=fake.name(), hospede_tipo=tipo, companhia=companhia,
            quarto=random.choice(quartos), categoria=categoria,
            categoria_id=cat_id[categoria], descricao=descricao,
            recebido=recebido, recebido_por=recebido_por,
            entregue=entregue, entregue_por=entregue_por,
            descartado=descartado, descartado_por=descartado_por,
            r_tipo=r_tipo, r_nome=r_nome,
            r_doc_tipo=r_doc_tipo, r_doc_final=r_doc_final,
        ))

    # Fase 2: ordena por chegada e atribui id e ticket em sequencia.
    registros.sort(key=lambda r: r["recebido"])
    tickets = gerar_tickets(len(registros))

    protocolos, anexos = [], []
    fmt = lambda d: d.strftime("%Y-%m-%d %H:%M:%S") if d else None

    for i, (r, ticket) in enumerate(zip(registros, tickets), start=1):
        protocolos.append((
            i, ticket, r["hospede_nome"], r["hospede_tipo"], r["companhia"],
            r["quarto"], r["categoria_id"], r["descricao"],
            fmt(r["recebido"]), r["recebido_por"],
            fmt(r["entregue"]), r["entregue_por"],
            fmt(r["descartado"]), r["descartado_por"],
            r["r_tipo"], r["r_nome"], r["r_doc_tipo"], r["r_doc_final"],
        ))

        anexos.append((i, "item", gerar_foto_item(i, r["categoria"], r["descricao"])))
        if r["entregue"]:
            anexos.append((i, "assinatura", gerar_assinatura(i)))
            if r["r_tipo"] == "terceiro":
                anexos.append((i, "documento", gerar_comprovante(i, "documento")))
                anexos.append((i, "autorizacao", gerar_comprovante(i, "autorizacao")))

    cur.executemany("""
        INSERT INTO protocolo
            (id, ticket, hospede_nome, hospede_tipo, companhia, quarto,
             categoria_id, descricao, recebido_em, recebido_por_id,
             entregue_em, entregue_por_id, descartado_em, descartado_por_id,
             retirado_por_tipo, retirado_por_nome,
             retirado_por_doc_tipo, retirado_por_doc_final)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, protocolos)

    cur.executemany(
        "INSERT INTO anexo (protocolo_id, tipo, arquivo_path) VALUES (?,?,?)",
        anexos)

    conn.commit()
    return len(protocolos), len(anexos)


def resumo(conn):
    print("\n--- status ---")
    for st, n in conn.execute(
            "SELECT status, COUNT(*) FROM vw_protocolo GROUP BY status ORDER BY 2 DESC"):
        print(f"  {st:<12} {n:>4}")

    print("\n--- volume e tempo medio por turno ---")
    for t, tp, tot, ativ, med in conn.execute("""
            SELECT turno_entrada, hospede_tipo, total_recebido,
                   ainda_ativos, media_horas_ate_retirada
            FROM vw_volume_turno ORDER BY hospede_tipo, turno_entrada"""):
        print(f"  {tp:<11} {t:<10} n={tot:<4} ativos={ativ:<3} media={med}h")

    n = conn.execute("SELECT COUNT(*) FROM vw_protocolo_vencido").fetchone()[0]
    print(f"\n--- aba de descarte: {n} protocolos vencidos ou em alerta ---")

    print("\n--- colisao de ticket entre protocolos ativos ---")
    linhas = list(conn.execute(
        "SELECT ticket, qtd_ativos, quartos, categorias FROM vw_ticket_colidido"))
    if not linhas:
        print("  nenhuma no momento")
    for t, q, quartos, cats in linhas:
        print(f"  ticket {t}: {q} ativos | quartos {quartos} | {cats}")

    largura = conn.execute(
        "SELECT length(ticket), COUNT(*) FROM protocolo GROUP BY 1").fetchall()
    print(f"\n--- digitos do ticket: {dict(largura)} ---")


if __name__ == "__main__":
    if not DB.exists():
        raise SystemExit("Banco nao existe. Roda 'python src/init_db.py' primeiro.")

    DIR_FOTOS.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    if conn.execute("SELECT COUNT(*) FROM protocolo").fetchone()[0]:
        raise SystemExit("Banco ja tem dados. Roda 'python src/init_db.py' para zerar.")

    np, na = popular(conn)
    print(f"{np} protocolos e {na} anexos inseridos.")
    resumo(conn)
    conn.close()