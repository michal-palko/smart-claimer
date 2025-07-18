import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from urllib.parse import quote_plus

METAAPP_DB_URL = (
    f"postgresql+psycopg2://{os.getenv('METAAPP_DB_USER')}:{quote_plus(os.getenv('METAAPP_DB_PASSWORD'))}"
    f"@{os.getenv('METAAPP_DB_HOST')}:{os.getenv('METAAPP_DB_PORT')}/{os.getenv('METAAPP_DB_NAME')}"
)

engine = create_engine(METAAPP_DB_URL, pool_pre_ping=True)
MetaAppSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def submit_to_metaapp(entry) -> int:
    """
    Submit a time entry to MetaApp database.
    Returns the vykaz_id if successful, raises an exception if failed.
    """
    with MetaAppSession() as session:
        result = session.execute(
            text("SELECT metaapp_metaapp_crm.insert_vykaz_entry(:login, :epic_tag, :jira, :datum, :hodiny, :minuty, :poznamka)"),
            {
                "login": entry.autor,
                "epic_tag": entry.uloha,
                "jira": entry.jira,
                "datum": entry.datum,
                "hodiny": entry.hodiny,
                "minuty": entry.minuty,
                "poznamka": entry.popis or ""
            }
        )
        vykaz_id = result.scalar()
        session.commit()
        return vykaz_id
