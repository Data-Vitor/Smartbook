-- =====================================================================
-- SMARTBOOK  |  schema.sql
-- Controle de protocolo de itens recebidos na portaria de hotel.
--
-- PRIVACIDADE: schema desenhado para minimizacao de dados.
-- Nenhum documento armazenado por inteiro (apenas 3 ultimos digitos).
-- Base de demonstracao 100% sintetica, gerada por script.
-- Nomes de companhia aerea sao informacao publica; a distribuicao
-- temporal de pernoite de tripulacao e INVENTADA, nao observada.
--
-- CONVENCOES
--   Datas/horas: TEXT ISO 8601 'YYYY-MM-DD HH:MM:SS', horario local SP.
--   Status:      derivado, nunca armazenado.
--   Turno:       derivado na consulta, nunca armazenado.
--   Arquivos:    banco guarda o CAMINHO, disco guarda o binario.
-- =====================================================================

PRAGMA foreign_keys = ON;


-- ---------------------------------------------------------------------
-- 1. colaborador
-- ---------------------------------------------------------------------
CREATE TABLE colaborador (
    id            INTEGER PRIMARY KEY,
    nome          TEXT    NOT NULL,
    turno_padrao  TEXT    CHECK (turno_padrao IN ('manha','tarde','madrugada')),
    ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1))
);


-- ---------------------------------------------------------------------
-- 2. categoria_item
-- ---------------------------------------------------------------------
CREATE TABLE categoria_item (
    id    INTEGER PRIMARY KEY,
    nome  TEXT NOT NULL UNIQUE
);

INSERT INTO categoria_item (nome) VALUES
    ('Encomenda'),
    ('Sacola'),
    ('Envelope'),
    ('Documento'),
    ('Flores'),
    ('Bagagem'),
    ('Outro');


-- ---------------------------------------------------------------------
-- 3. protocolo
--
-- Hospede desnormalizado de proposito: normalizar exigiria modelar
-- estadia, e o par nome/quarto so e estavel dentro de uma estadia.
--
-- hospede_tipo separa hospede comum de tripulante. Sao dois publicos
-- com comportamento distinto (horario de chegada, tempo ate retirada,
-- tipo de item) e a separacao e o que torna o analytics interessante.
--
-- Documento: apenas os 3 ultimos digitos. Suficiente para conferir
-- contra o documento em maos, inutil para vazamento.
--
-- CICLO DE VIDA
--   ativo       -> entregue_em IS NULL AND descartado_em IS NULL
--   entregue    -> entregue_em preenchido
--   descartado  -> descartado_em preenchido (politica: 180 dias)
-- ---------------------------------------------------------------------
CREATE TABLE protocolo (
    id                     INTEGER PRIMARY KEY,

    -- destinatario
    hospede_nome           TEXT    NOT NULL,
    hospede_tipo           TEXT    NOT NULL DEFAULT 'hospede'
                                   CHECK (hospede_tipo IN ('hospede','tripulante')),
    companhia              TEXT,               -- so para tripulante
    quarto                 TEXT    NOT NULL,   -- TEXT: quarto pode ter letra

    -- o item
    categoria_id           INTEGER NOT NULL REFERENCES categoria_item(id),
    descricao              TEXT,
    observacao             TEXT,

    -- entrada
    recebido_em            TEXT    NOT NULL,
    recebido_por_id        INTEGER NOT NULL REFERENCES colaborador(id),

    -- saida por entrega
    entregue_em            TEXT,
    entregue_por_id        INTEGER REFERENCES colaborador(id),

    -- saida por descarte (politica de 180 dias)
    descartado_em          TEXT,
    descartado_por_id      INTEGER REFERENCES colaborador(id),

    -- comprovacao de retirada
    retirado_por_tipo      TEXT CHECK (retirado_por_tipo IN ('destinatario','terceiro')),
    retirado_por_nome      TEXT,               -- NULL quando tipo = destinatario
    retirado_por_doc_tipo  TEXT CHECK (retirado_por_doc_tipo IN ('RG','CNH','Passaporte','Outro')),
    retirado_por_doc_final TEXT,               -- SOMENTE os 3 ultimos digitos

    criado_em              TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    -- ---- regras de integridade ----

    -- Um item nao pode ser entregue e descartado.
    CHECK (entregue_em IS NULL OR descartado_em IS NULL),

    -- Protocolo ativo nao pode ter vestigio de retirada.
    CHECK (
        entregue_em IS NOT NULL
        OR (entregue_por_id       IS NULL
        AND retirado_por_tipo     IS NULL
        AND retirado_por_nome     IS NULL
        AND retirado_por_doc_tipo IS NULL)
    ),

    -- Protocolo entregue exige quem entregou e sob que tipo de retirada.
    CHECK (
        entregue_em IS NULL
        OR (entregue_por_id   IS NOT NULL
        AND retirado_por_tipo IS NOT NULL)
    ),

    -- Retirada por terceiro exige o nome de quem retirou.
    CHECK (
        retirado_por_tipo IS NULL
        OR retirado_por_tipo = 'destinatario'
        OR retirado_por_nome IS NOT NULL
    ),

    -- Descarte exige responsavel.
    CHECK (descartado_em IS NULL OR descartado_por_id IS NOT NULL),

    -- Companhia so faz sentido para tripulante.
    CHECK (hospede_tipo = 'tripulante' OR companhia IS NULL),

    -- Documento nunca completo.
    CHECK (retirado_por_doc_final IS NULL OR length(retirado_por_doc_final) <= 3),

    -- Saida nao pode ser anterior a entrada.
    CHECK (entregue_em   IS NULL OR entregue_em   >= recebido_em),
    CHECK (descartado_em IS NULL OR descartado_em >= recebido_em)
);


-- ---------------------------------------------------------------------
-- 4. anexo
-- Foto do item, assinatura, documento e autorizacao vivem todos aqui.
-- Tabela separada em vez de colunas fixas porque documento tem frente
-- e verso, e autorizacao pode vir como email + print.
--
-- A lista principal do app NAO consulta esta tabela. So a tela de
-- detalhe. O JOIN fica fora do caminho mais usado.
--
-- REGRA DE NEGOCIO (validada na aplicacao, nao aqui):
--   retirada por destinatario -> exige 'assinatura'
--   retirada por terceiro     -> exige 'assinatura' + 'documento' + 'autorizacao'
-- SQLite nao valida condicao entre tabelas, e a mensagem de erro para
-- o usuario fica melhor vindo do Python.
-- ---------------------------------------------------------------------
CREATE TABLE anexo (
    id            INTEGER PRIMARY KEY,
    protocolo_id  INTEGER NOT NULL REFERENCES protocolo(id) ON DELETE CASCADE,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('item','assinatura','documento','autorizacao')),
    arquivo_path  TEXT    NOT NULL,
    criado_em     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);


-- ---------------------------------------------------------------------
-- 5. verificacao  (arquitetura pronta, NAO ativada)
-- Gancho para codigo OTP e aviso de descarte por SMS/email. Hoje a
-- funcao notificar() apenas grava aqui. Trocar o corpo dela por uma
-- chamada de API nao exige mudanca de schema.
-- Nao ativado por decisao de custo (API paga).
-- ---------------------------------------------------------------------
CREATE TABLE verificacao (
    id            INTEGER PRIMARY KEY,
    protocolo_id  INTEGER NOT NULL REFERENCES protocolo(id) ON DELETE CASCADE,
    canal         TEXT    NOT NULL CHECK (canal IN ('sms','email')),
    finalidade    TEXT    NOT NULL CHECK (finalidade IN ('chegada','retirada','aviso_descarte')),
    codigo        TEXT,
    enviado_em    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    validado_em   TEXT
);


-- =====================================================================
-- INDICES
-- Cobrem as consultas quentes: lista de ativos, busca por hospede,
-- ordenacao por data.
-- =====================================================================
CREATE INDEX idx_protocolo_ativo    ON protocolo(recebido_em)
    WHERE entregue_em IS NULL AND descartado_em IS NULL;
CREATE INDEX idx_protocolo_recebido ON protocolo(recebido_em DESC);
CREATE INDEX idx_protocolo_hospede  ON protocolo(hospede_nome);
CREATE INDEX idx_protocolo_quarto   ON protocolo(quarto);
CREATE INDEX idx_anexo_protocolo    ON anexo(protocolo_id, tipo);


-- =====================================================================
-- VIEWS
-- =====================================================================

-- ---------------------------------------------------------------------
-- vw_protocolo
-- Visao completa com status, turno, tempo e alerta de descarte
-- ja calculados. Base de tudo que o app le.
--
-- Turnos: manha 07-15, tarde 15-23, madrugada 23-07.
-- Politica de descarte: 180 dias. Alerta a partir de 150.
-- ---------------------------------------------------------------------
CREATE VIEW vw_protocolo AS
SELECT
    p.id,
    p.hospede_nome,
    p.hospede_tipo,
    p.companhia,
    p.quarto,
    c.nome                                 AS categoria,
    p.descricao,
    p.recebido_em,
    rec.nome                               AS recebido_por,
    p.entregue_em,
    ent.nome                               AS entregue_por,
    p.descartado_em,
    p.retirado_por_tipo,
    p.retirado_por_nome,

    CASE
        WHEN p.descartado_em IS NOT NULL THEN 'descartado'
        WHEN p.entregue_em   IS NOT NULL THEN 'entregue'
        ELSE 'ativo'
    END                                    AS status,

    CASE
        WHEN CAST(strftime('%H', p.recebido_em) AS INTEGER) BETWEEN  7 AND 14 THEN 'manha'
        WHEN CAST(strftime('%H', p.recebido_em) AS INTEGER) BETWEEN 15 AND 22 THEN 'tarde'
        ELSE 'madrugada'
    END                                    AS turno_entrada,

    -- horas entre entrada e saida; para ativos, horas ate agora
    ROUND(
        (julianday(COALESCE(p.entregue_em, p.descartado_em, datetime('now','localtime')))
         - julianday(p.recebido_em)) * 24
    , 1)                                   AS horas_permanencia,

    CAST(
        julianday(COALESCE(p.entregue_em, p.descartado_em, datetime('now','localtime')))
        - julianday(p.recebido_em)
    AS INTEGER)                            AS dias_permanencia,

    CASE
        WHEN p.entregue_em IS NOT NULL OR p.descartado_em IS NOT NULL THEN NULL
        WHEN julianday(datetime('now','localtime')) - julianday(p.recebido_em) >= 180 THEN 'vencido'
        WHEN julianday(datetime('now','localtime')) - julianday(p.recebido_em) >= 150 THEN 'alerta'
        ELSE 'ok'
    END                                    AS situacao_descarte

FROM protocolo p
JOIN categoria_item   c   ON c.id   = p.categoria_id
JOIN colaborador      rec ON rec.id = p.recebido_por_id
LEFT JOIN colaborador ent ON ent.id = p.entregue_por_id;


-- ---------------------------------------------------------------------
-- vw_protocolo_ativo
-- Alimenta a tela principal e o contador "Protocolos ativos: X".
-- ---------------------------------------------------------------------
CREATE VIEW vw_protocolo_ativo AS
SELECT *
FROM vw_protocolo
WHERE status = 'ativo'
ORDER BY recebido_em DESC;


-- ---------------------------------------------------------------------
-- vw_protocolo_vencido
-- Aba de descarte: itens que passaram da politica de 180 dias e ainda
-- estao no estoque. Ordena do mais antigo para o mais novo.
-- ---------------------------------------------------------------------
CREATE VIEW vw_protocolo_vencido AS
SELECT *
FROM vw_protocolo
WHERE status = 'ativo'
  AND situacao_descarte IN ('vencido','alerta')
ORDER BY recebido_em ASC;


-- ---------------------------------------------------------------------
-- vw_volume_turno
-- Analytics: volume e tempo medio por turno e por tipo de publico.
-- ---------------------------------------------------------------------
CREATE VIEW vw_volume_turno AS
SELECT
    turno_entrada,
    hospede_tipo,
    COUNT(*)                                           AS total_recebido,
    SUM(CASE WHEN status = 'ativo' THEN 1 ELSE 0 END)  AS ainda_ativos,
    ROUND(AVG(CASE WHEN status = 'entregue'
                   THEN horas_permanencia END), 1)     AS media_horas_ate_retirada
FROM vw_protocolo
GROUP BY turno_entrada, hospede_tipo;
