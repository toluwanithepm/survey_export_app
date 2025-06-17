from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class SurveyConfig(Base):
    __tablename__ = 'survey_config_entity'
    survey_config_id = Column(Integer, primary_key=True)
    type = Column(String)
    name = Column(String)
    description = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class SurveyQuestion(Base):
    __tablename__ = 'survey_question_entity'
    survey_question_id = Column(Integer, primary_key=True)
    survey_config_id = Column(Integer, ForeignKey('survey_config_entity.survey_config_id'))
    order = Column(Integer)
    question = Column(Text)
    options = Column(Text)
    type = Column(String)
    pre_question_id = Column(Integer)
    pre_question_value = Column(String)
    comparator = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    config = relationship('SurveyConfig')

class SurveyAnswer(Base):
    __tablename__ = 'survey_answer_entity'
    unique_member_id = Column(String, primary_key=True)
    survey_question_id = Column(Integer, ForeignKey('survey_question_entity.survey_question_id'), primary_key=True)
    survey_log_id = Column(Integer, primary_key=True)
    ik_number = Column(String)
    answer = Column(Text)
    date_logged = Column(DateTime)
    staff_id = Column(Integer)
    app_version = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    operator_id = Column(Integer)
    desc = Column(Text)
    unique_entity_id = Column(String)
    question = relationship('SurveyQuestion')