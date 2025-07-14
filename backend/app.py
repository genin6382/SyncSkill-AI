from flask import Flask
from models import db , Conversation , User , Resume
from flask import request, jsonify , session
from flask_cors import CORS
import requests
from werkzeug.exceptions import RequestEntityTooLarge
import os
import json
from job_query_processor import JobQueryProcessor
from vector_store import load_vector_store

app = Flask(__name__)

CORS(app, origins=["http://localhost:5173"], supports_credentials=True)

# Replace with your actual MySQL database credentials
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Vidhulinux@localhost/resume'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 

app.secret_key = os.urandom(24)

db.init_app(app)

with app.app_context():
    db.create_all()


LAMBDA_FUNCTION_URL = "https://7q3cud6m6ncy2g5nx7gjh5oux40iumyi.lambda-url.ap-southeast-2.on.aws/"  
LAMBDA_GET_TEXT_URL = "https://2efw3f5raastftivhjah6xbcv40hqnne.lambda-url.ap-southeast-2.on.aws/"


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({"error": "File size exceeds 1MB limit"}), 413


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'User already exists'}), 400

    new_user = User(username=username, password=password)
    try :
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error occurred: {str(e)}'}), 500

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username, password=password).first()

    if not user:
        return jsonify({'message': 'Invalid credentials'}), 401
    
    session['user_id'] = user.id
    session['username'] = user.username
    return jsonify({'message': 'Login successful', 'user_id': user.id}), 200

@app.route('/api/check-auth', methods= ['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            "isAuthenticated": True, 
            "user": {
                "id": session['user_id'],
                "username": session['username']
            }
        }), 200
    return jsonify({"isAuthenticated": False}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    #delete the conversation for that user
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        Conversation.query.filter_by(user_id=session['user_id']).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error occurred: {str(e)}'}), 500
    # Clear the session
    session.pop('user_id', None)
    session.pop('username', None)
    return jsonify({'message': 'Logout successful'}), 200

@app.route('/api/conversations', methods = ['GET','POST'])
def get_conversations():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401
    
    if request.method == 'GET': 
        conversations = Conversation.query.filter_by(user_id=session['user_id']).order_by(Conversation.timestamp.asc()).all()
        conversations_list = [{'id': conv.id, 'question': conv.question,'answer': conv.answer, 'timestamp': conv.timestamp} for conv in conversations]
        return jsonify(conversations_list), 200
    
    elif request.method == 'POST':
        data = request.get_json()
        question = data.get('question')
        answer = data.get('answer')

        if not question or not answer:
            return jsonify({'message': 'Content is required'}), 400

        new_conversation = Conversation(user_id=session['user_id'], question=question, answer=answer)
        try:
            db.session.add(new_conversation)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'Error occurred: {str(e)}'}), 500

        return jsonify({'message': 'Conversation created successfully', 'id': new_conversation.id}), 201

@app.route("/api/upload", methods=["POST"])
def upload_resume():
    try:
        if "resume" not in request.files or "user_id" not in session:
            return jsonify({"error": "Missing file or user_id"}), 400

        resume_file = request.files["resume"]
    
        if resume_file.content_length and resume_file.content_length > 1024 * 1024:
            return jsonify({"error": "File size exceeds 1MB limit"}), 413
        
        file_content = resume_file.read()
        if len(file_content) > 1024 * 1024:
            return jsonify({"error": "File size exceeds 1MB limit"}), 413
        
        resume_file.seek(0)
        
        files = {
            "resume": (resume_file.filename, file_content, resume_file.content_type)
        }
        data = {
            "user_id": session['user_id'] 
        }
        
        lambda_response = requests.post(LAMBDA_FUNCTION_URL, files=files, data=data)
        lambda_json = lambda_response.json()        

        if lambda_response.status_code == 200:
            return jsonify({
                "message": lambda_json.get("message", "Upload successful")
            }), 200
        else:
            return jsonify({
                "error": lambda_json.get("error", "Unknown error from Lambda")
            }), lambda_response.status_code

    except RequestEntityTooLarge:
        return jsonify({"error": "File size exceeds 1MB limit"}), 413
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to upload to Lambda"}), 500
    
@app.route("/api/get-processed-text", methods=["GET"])
def get_processed_text():
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401
            
        # Wait 5 seconds before processing (allows time for Textract to complete)
        import time
        time.sleep(5)
            
        response = requests.post(
            LAMBDA_GET_TEXT_URL,
            json={"user_id": user_id}
        )
        
        if response.status_code == 200:
            # Parse the response from Lambda Function URL
            lambda_response = response.json()
            body_data = lambda_response

            if 'text' in body_data :
                if Resume.query.filter_by(user_id=user_id).first():
                    # If a resume already exists for this user, delete it
                    Resume.query.filter_by(user_id=user_id).delete()
                    db.session.commit()

                resume = Resume(
                    user_id=user_id, 
                    extracted_text=body_data['text'], 
                    file_path=body_data['file_path']
                )
                
                db.session.add(resume)
                db.session.commit()
                
                return jsonify({
                    "message": "Successfully fetched resume text",
                    "word_count": body_data.get('word_count', 0),
                    "line_count": body_data.get('line_count', 0)
                }), 200
            else:
                return jsonify({
                    "error": "Text not found in Lambda response",
                    "details": body_data
                }), 400
        else:
            return jsonify({
                "error": "Failed to fetch resume text from Lambda",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return jsonify({"error": "Invalid JSON response from Lambda"}), 500
    except Exception as e:
        print("Error fetching processed text:", e)
        return jsonify({"error": "Unexpected error occurred"}), 500

# Global services
job_vectorstore = None
query_processor = None

def initialize_app():
    """Initialize the application with job vectorstore and query processor"""
    global job_vectorstore, query_processor

    print("Initializing application...")

    job_vectorstore = load_vector_store()

    if job_vectorstore.collection.count() == 0:
        print("Vector store is empty. Make sure chroma_setup.py was run successfully.")
        return False

    query_processor = JobQueryProcessor(job_vectorstore)

    print("Application initialized successfully!")
    return True

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'vectorstore_ready': job_vectorstore is not None,
        'processor_ready': query_processor is not None
    })

@app.route('/api/job-query', methods=['POST'])
def job_query():
    """
    Endpoint for job-related queries.
    Expected JSON:
    {
        "query": "What roles am I eligible for?",
        "user_id": 123
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        user_id = data.get('user_id') or session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400

        resume = Resume.query.filter_by(user_id=user_id).first()
        if not resume or not resume.extracted_text:
            return jsonify({'error': 'No valid resume found for this user'}), 404

        if not query_processor:
            return jsonify({'error': 'Query processor not initialized'}), 500

        result = query_processor.process_query(query, resume.extracted_text)

        if not result['success']:
            return jsonify({'error': result['message']}), 400
        
        print(f"Query: {query}, User ID: {user_id}, Total Matches: {result['total_matches']}")
        print(f"Response: {result['response']}")

        return jsonify({
            'success': True,
            'query': query,
            'response': result['response'],
            'total_matches': result['total_matches'],
            'user_id': user_id
        })

    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

if __name__ == '__main__':
    if initialize_app():
        app.run(debug=True, host="0.0.0.0", port=5000)
    else:
        print("App failed to initialize.")

