import io
import os
from urllib import response
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
    
    # if not survey_id_param:
    #     return "Survey ID is required", 400
    
    # # Use the parameter as-is if it's already in the correct format
    # # or extract numeric part if needed
    # if isinstance(survey_id_param, str) and survey_id_param.startswith('survey_config_'):
    #     # If your database stores the full "survey_config_74" format, use this
    #     survey_id = survey_id_param
    # else:
    #     # If your database stores just the numeric part, try to extract it
    #     try:
    #         numeric_id = int(survey_id_param)
    #         survey_id = str(numeric_id)  # Convert to string for text column
    #     except (ValueError, TypeError):
    #         return "Invalid survey ID format", 400
    
    session = Session()
    
    try:
        # First, let's check if the survey exists
        survey_exists = session.query(SurveyConfig).filter(SurveyConfig.survey_config_id == survey_id).first()
        if not survey_exists:
            return f"Survey with ID {survey_id} not found", 404
        
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
        df = pd.read_sql(query.statement, engine, params=query.statement.compile().params)
        
        print(f"DataFrame shape: {df.shape}")  # Debug info
        print(f"DataFrame columns: {df.columns.tolist()}")  # Debug info
        
        if df.empty:
            # Let's check if there are any questions for this survey
            questions_query = session.query(SurveyQuestion).filter(SurveyQuestion.survey_config_id == survey_id)
            questions_count = questions_query.count()
            
            # Let's check if there are any answers for questions in this survey
            answers_query = session.query(SurveyAnswer).join(SurveyQuestion).filter(SurveyQuestion.survey_config_id == survey_id)
            answers_count = answers_query.count()
            
            return f"No data found for survey {survey_id}. Survey has {questions_count} questions and {answers_count} total answers.", 404
        
        # Print first few rows for debugging
        print("First 3 rows of data:")
        print(df.head(3).to_string())
        
        # Check if we have the required columns for pivoting
        required_cols = ['unique_member_id', 'question_text', 'answer']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return f"Missing required columns for pivot: {missing_cols}", 500
        
        # Create a simpler pivot first to test
        try:
            # Group by response (unique_member_id + date_logged combination)
            pivot_df = df.pivot_table(
                index=[
                    'survey_config_id', 
                    'unique_member_id', 
                    'date_logged'  # Use fewer columns initially to test
                ],
                columns='question_text',
                values='answer',
                aggfunc='first'
            ).reset_index()
            
            print(f"Pivot DataFrame shape: {pivot_df.shape}")  # Debug info
            
        except Exception as pivot_error:
            print(f"Pivot error: {str(pivot_error)}")
            # If pivot fails, return the raw data as CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            
            csv_bytes = io.BytesIO(csv_buffer.getvalue().encode('utf-8'))
            
            return send_file(
                csv_bytes,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'survey_{survey_id}_raw_data.csv'
            )
            # Add headers to force CSV download
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename=survey_{survey_id}_raw_data.csv'
            
            return response
        # Clean up column names
        pivot_df.columns.name = None
        
        # Create CSV buffer
        csv_buffer = io.StringIO()
        pivot_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        print(f"CSV buffer length: {len(csv_buffer.getvalue())}")  # Debug info
        
        # Convert to bytes for download
        csv_bytes = io.BytesIO(csv_buffer.getvalue().encode('utf-8'))
        
        # Create the response with explicit headers
        response = send_file(
            csv_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'survey_{survey_id}_responses.csv'
        )
        
        # Add additional headers to force CSV download
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=survey_{survey_id}_responses.csv'
        
        return response
        
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