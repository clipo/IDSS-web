
from flask import render_template
from flask import Flask, request, redirect, url_for
from werkzeug import secure_filename
import os
from seriation import IDSS



UPLOAD_FOLDER = '/var/www/uploads/data/'
ALLOWED_EXTENSIONS = set(['txt'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    author = "Me"
    name = "You"
    return render_template('index.html', author=author, name=name)

@app.route('/about')
def about():
    return 'The about page'

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath=(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.save(filepath)
            errors = check_file_for_valid_input(filename)


            return redirect(url_for('uploaded_file',
                                    filename=filename))

def check_file_for_valid_input(filename):
    problems = 0
    open(filename)
    return problems

if __name__ == '__main__':
    app.run()
