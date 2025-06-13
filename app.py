import io
import os
from flask import Flask, render_template, send_file, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import pandas as pd

from models import SurveyConfig, SurveyQuestion, SurveyAnswer

# Load environment
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Initialize app & DB
app = Flask(__name__)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    session = Session()
    total = session.query(SurveyConfig).count()
    surveys = (
        session.query(SurveyConfig)
        .order_by(SurveyConfig.survey_config_id)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    session.close()

    if not surveys:
        return render_template('empty.html')

    total_pages = (total + limit - 1) // limit
    return render_template('index.html', surveys=surveys,
                           page=page, limit=limit,
                           total=total, total_pages=total_pages)

@app.route('/download')
def download():
    survey_id = request.args.get('survey_config_id', type=int)
    session = Session()
    df = pd.read_sql(
        session.query(
            SurveyAnswer.unique_member_id,
            SurveyAnswer.survey_log_id,
            SurveyAnswer.answer.label('answer_text'),
            SurveyQuestion.survey_config_id,
            SurveyQuestion.question.label('question_text'),
            SurveyConfig.name.label('survey_name')
        )
        .join(SurveyQuestion, SurveyAnswer.survey_question_id == SurveyQuestion.survey_question_id)
        .join(SurveyConfig, SurveyQuestion.survey_config_id == SurveyConfig.survey_config_id)
        .filter(SurveyQuestion.survey_config_id == survey_id)
        .order_by(SurveyAnswer.unique_member_id, SurveyAnswer.survey_log_id, SurveyQuestion.order)
        .statement, engine)
    session.close()

    wide = (df.pivot_table(
        index=['unique_member_id', 'survey_log_id', 'survey_config_id', 'survey_name'],
        columns='question_text', values='answer_text', aggfunc='first')
        .reset_index())
    wide.columns.name = None

    buf = io.StringIO()
    wide.to_csv(buf, index=False)
    buf.seek(0)

    return send_file(
        io.BytesIO(buf.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'survey_{survey_id}_responses.csv'
    )

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
                           message='Looks like this page took a coffee break.'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500,
                           message='Something went sideways on our end.'), 500

if __name__ == '__main__':
    app.run(debug=True)