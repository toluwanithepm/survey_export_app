import io
import os
import re
from flask import Flask, render_template, send_file, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import pandas as pd

from models import SurveyConfig, SurveyQuestion, SurveyAnswer

# Load environment
load_dotenv()
env_url = os.getenv('DATABASE_URL')
if not env_url:
    raise RuntimeError("DATABASE_URL is not set in environment variables")

# Initialize Flask and DB
app = Flask(__name__)
engine = create_engine(env_url)
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
    raw_id = request.args.get('survey_config_id')
    if not raw_id:
        return "Missing survey_config_id", 400
    # Extract numeric ID suffix
    match = re.search(r"(\d+)$", raw_id)
    if not match:
        return "Invalid survey_config_id format", 400
    survey_id = int(match.group(1))

    session = Session()
    # Join answer and question tables
    query = (
        session.query(
            SurveyQuestion.survey_config_id,
            SurveyAnswer.unique_member_id,
            SurveyAnswer.survey_question_id,
            SurveyAnswer.survey_log_id,
            SurveyAnswer.ik_number,
            SurveyAnswer.answer,
            SurveyAnswer.date_logged,
            SurveyAnswer.staff_id,
            SurveyAnswer.app_version,
            SurveyAnswer.created_at.label('answer_created_at'),
            SurveyAnswer.updated_at.label('answer_updated_at'),
            SurveyAnswer.operator_id,
            SurveyAnswer.desc,
            SurveyAnswer.unique_entity_id,
            SurveyQuestion.question.label('question_text')
        )
        .join(SurveyQuestion, SurveyAnswer.survey_question_id == SurveyQuestion.survey_question_id)
        .filter(SurveyQuestion.survey_config_id == survey_id)
        .order_by(SurveyAnswer.unique_member_id,
                  SurveyAnswer.survey_log_id,
                  SurveyQuestion.order)
    )
    df = pd.read_sql(query.statement, engine)
    session.close()

    if df.empty:
        return render_template('error.html', code=404, message='No responses found for this survey.'), 404

    # Pivot to transpose responses
    pivot_idx = [
        'survey_config_id', 'unique_member_id', 'survey_question_id',
        'survey_log_id', 'ik_number', 'date_logged', 'staff_id',
        'app_version', 'answer_created_at', 'answer_updated_at',
        'operator_id', 'desc', 'unique_entity_id'
    ]
    df['question_text'] = df['question_text'].str.strip()
    wide = (
        df.pivot_table(
            index=pivot_idx,
            columns='question_text',
            values='answer',
            aggfunc='first'
        ).reset_index()
    )
    wide.columns.name = None

    # Export CSV
    buf = io.StringIO()
    wide.to_csv(buf, index=False)
    buf.seek(0)
    csv_bytes = buf.getvalue().encode('utf-8')

    return send_file(
        io.BytesIO(csv_bytes),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'survey_{survey_id}_responses.csv'
    )

@app.route('/api/surveys')
def api_surveys():
    session = Session()
    surveys = session.query(SurveyConfig).order_by(SurveyConfig.survey_config_id).all()
    session.close()
    data = [
        { 'id': f'survey_config_{s.survey_config_id}', 'name': s.name, 'description': s.description }
        for s in surveys
    ]
    return jsonify(data)

# Error handlers
def render_error(code, message):
    return render_template('error.html', code=code, message=message), code

@app.errorhandler(404)
def handle_404(e):
    return render_error(404, 'Page not found.')

@app.errorhandler(500)
def handle_500(e):
    return render_error(500, 'Internal server error.')

if __name__ == '__main__':
    app.run(debug=True)