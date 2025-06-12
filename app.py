import io
import os
from flask import Flask, render_template, send_file, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

from models import Base, SurveyConfig, SurveyQuestion, SurveyAnswer

app = Flask(__name__)
# Update your DATABASE_URL accordingly
DATABASE_URL = os.getenv("DATABASE_URL")  # Load from environment
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

@app.route('/')
def index():
    session = Session()
    surveys = session.query(SurveyConfig).all()
    session.close()
    return render_template('index.html', surveys=surveys)

@app.route('/download')
def download():
    survey_id = request.args.get('survey_config_id', type=int)
    session = Session()

    # Query joined data
    query = (
        session.query(
            SurveyAnswer.unique_member_id,
            SurveyAnswer.survey_log_id,
            SurveyAnswer.answer.label('answer_text'),
            SurveyAnswer.date_logged,
            SurveyQuestion.survey_config_id,
            SurveyQuestion.question.label('question_text'),
            SurveyConfig.name.label('survey_name')
        )
        .join(SurveyQuestion, SurveyAnswer.survey_question_id == SurveyQuestion.survey_question_id)
        .join(SurveyConfig, SurveyQuestion.survey_config_id == SurveyConfig.survey_config_id)
        .filter(SurveyQuestion.survey_config_id == survey_id)
        .order_by(SurveyAnswer.unique_member_id, SurveyAnswer.survey_log_id, SurveyQuestion.order)
    )
    df = pd.read_sql(query.statement, engine)
    session.close()

    # Pivot to wide form
    wide = (
        df
        .pivot_table(
            index=['unique_member_id', 'survey_log_id', 'survey_config_id', 'survey_name'],
            columns='question_text',
            values='answer_text',
            aggfunc='first'
        )
        .reset_index()
    )
    wide.columns.name = None

    # Export to CSV in-memory
    buf = io.StringIO()
    wide.to_csv(buf, index=False)
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        attachment_filename=f'survey_{survey_id}_responses.csv'
    )

if __name__ == '__main__':
    app.run(debug=True)