import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import PyPDF2

# Create Flask app
app = Flask(__name__)

# Set upload folder from environment variable or default path
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', './uploads')

# Route for method 1 to print a message
@app.route('/method1', methods=['GET'])
def method1():
    return "Method 1"

# Route to take a PDF input and give the report (text extracted) as output
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Extract text from PDF
        with open(filepath, 'rb') as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            text = ''
            for page in reader.pages:
                text += page.extract_text()

        # Simple report as extracted text
        report = {"report": text}
        return jsonify(report)

    return jsonify({"error": "Invalid file type. Only PDFs allowed."}), 400

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
