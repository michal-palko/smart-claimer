from sqlalchemy import Column, Integer, String, Date, Text, TIMESTAMP, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TimeEntry(Base):
    __tablename__ = "time_entry"
    id = Column(Integer, primary_key=True, index=True)
    uloha = Column(Text, nullable=False)
    autor = Column(String, nullable=False)
    datum = Column(Date, nullable=False)
    hodiny = Column(Integer, nullable=False)
    minuty = Column(Integer, nullable=False)
    jira = Column(String, nullable=True)
    popis = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    modified_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    submitted_to_metaapp_at = Column(TIMESTAMP(timezone=True), nullable=True)
    jira_name = Column(Text, nullable=True)
    uloha_name = Column(Text, nullable=True)
    metaapp_vykaz_id = Column(Integer, nullable=True)

class Template(Base):
    __tablename__ = "template"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    uloha = Column(Text, nullable=True)
    autor = Column(String, nullable=False)
    hodiny = Column(String, nullable=True)
    minuty = Column(String, nullable=True)
    jira = Column(String, nullable=True)
    popis = Column(Text, nullable=True)
