import io
import os
from flask import Flask, render_template, send_file, request, jsonify
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
    return render_template('index.html', 
                         surveys=surveys, 
                         page=page, 
                         limit=limit, 
                         total=total, 
                         total_pages=total_pages)

@app.route('/download')
def download():
    survey_id = request.args.get('survey_config_id')  # remove `type=int`

    if not survey_id_param:
        return "Survey ID is required", 400
    
    # Extract numeric ID if it's in format "survey_config_74"
    if isinstance(survey_id_param, str) and survey_id_param.startswith('survey_config_'):
        try:
            survey_id = int(survey_id_param.replace('survey_config_', ''))
        except ValueError:
            return "Invalid survey ID format", 400
    else:
        # Try to convert to int directly
        try:
            survey_id = int(survey_id_param)
        except (ValueError, TypeError):
            return "Invalid survey ID format", 400
    
    session = Session()
    
    try:
        # Query to get all survey response data with proper joins
        query = session.query(
            SurveyConfig.survey_config_id,
            SurveyAnswer.unique_member_id,
            SurveyQuestion.survey_question_id,
            SurveyAnswer.ik_number,
            SurveyAnswer.answer,
            SurveyAnswer.date_logged,
            SurveyAnswer.staff_id,
            SurveyAnswer.app_version,
            SurveyAnswer.created_at,
            SurveyAnswer.updated_at,
            SurveyAnswer.operator_id,
            SurveyAnswer.desc,
            SurveyAnswer.unique_entity_id,
            SurveyQuestion.question.label('question_text'),
            SurveyQuestion.order.label('question_order')
        ).select_from(SurveyAnswer)\
        .join(SurveyQuestion, SurveyAnswer.survey_question_id == SurveyQuestion.survey_question_id)\
        .join(SurveyConfig, SurveyQuestion.survey_config_id == SurveyConfig.survey_config_id)\
        .filter(SurveyConfig.survey_config_id == survey_id)\
        .order_by(SurveyAnswer.unique_member_id, SurveyAnswer.date_logged, SurveyQuestion.order)
        
        # Execute query and create DataFrame
        df = pd.read_sql(query.statement, engine)
        
        if df.empty:
            return "No data found for the specified survey", 404
        
        # Create the transposed CSV
        # First, create a pivot table for the answers
        pivot_df = df.pivot_table(
            index=[
                'survey_config_id', 
                'unique_member_id', 
                'ik_number',
                'date_logged',
                'staff_id',
                'app_version',
                'created_at',
                'updated_at',
                'operator_id',
                'desc',
                'unique_entity_id'
            ],
            columns='question_text',
            values='answer',
            aggfunc='first'
        ).reset_index()
        
        # Clean up column names
        pivot_df.columns.name = None
        
        # Create CSV buffer
        csv_buffer = io.StringIO()
        pivot_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        # Convert to bytes for download
        csv_bytes = io.BytesIO(csv_buffer.getvalue().encode('utf-8'))
        
        return send_file(
            csv_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'survey_{survey_id}_responses.csv'
        )
        
    except Exception as e:
        return f"Error generating CSV: {str(e)}", 500
    finally:
        session.close()

@app.route('/api/surveys')
def api_surveys():
    # Return full list of surveys for real-time updates
    session = Session()
    try:
        surveys = session.query(SurveyConfig).order_by(SurveyConfig.survey_config_id).all()
        data = [
            {
                'id': s.survey_config_id,
                'name': s.name,
                'description': s.description
            }
            for s in surveys
        ]
        return jsonify(data)
    finally:
        session.close()

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', 
                         code=404, 
                         message='Looks like this page took a coffee break.'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', 
                         code=500, 
                         message='Something went sideways on our end.'), 500

if __name__ == '__main__':
    app.run(debug=True)