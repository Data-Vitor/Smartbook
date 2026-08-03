import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "smartbook.db"


def achar_schema():
    encontrados = list(RAIZ.rglob("schema.sql"))
    if not encontrados:
        raise FileNotFoundError(f"schema.sql nao encontrado dentro de {RAIZ}.")
    return encontrados[0]


def criar_banco(recriar=False):
    schema = achar_schema()
    print(f"Schema encontrado: {schema}")

    if recriar and DB.exists():
        DB.unlink()

    DB.parent.mkdir(parents=True, exist_ok=True)
    (RAIZ / "data" / "fotos").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.executescript(schema.read_text(encoding="utf-8"))
    conn.commit()
    tabelas = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    conn.close()

    print(f"Banco criado em {DB}")
    print(f"Tabelas: {tabelas}")


if __name__ == "__main__":
    criar_banco(recriar=True)
