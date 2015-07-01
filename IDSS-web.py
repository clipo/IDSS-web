
from flask import render_template
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os.path
import os
from seriation import IDSS
import uuid
import csv
from pyparsing import *
import sqlite3 as lite
import sys
import zipfile
import subprocess

DATABASE_NAME = './database/idssProcessing.sqlite'
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
    return render_template('index.html')

@app.route('/about')
def about():
    return 'The about page'

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['filename']
    if file and allowed_file(file.filename):
        jobname=create_job()
        filepath = app.config['UPLOAD_FOLDER']+jobname+"/"
        filename=(os.path.join(filepath, file.filename))
        file.save(filename)
        problems = check_file_for_valid_input(filename)
        if problems is not None:
            render_template('/index.html', problems=problems)
        else:
            run_idss(filename,filepath,jobname)
            return redirect(url_for('/processing',
                                filename=filename, path=filepath, jobname=jobname))

@app.route('/processing')
def check_to_see_if_done():
    filename = request.args['filename']
    path = request.args['path']
    resultsfile=filename[:-4]+"-continuity-minmax-by-weight.png"
    if os.path.isfile(resultsfile):
        zippedpath=zipresults(filename, path)
    else:
        return redirect(url_for('/processing', filename=filename, path=path))
    return zippedpath

# This route is expecting a parameter containing the name
# of a file. Then it will locate that file on the upload
# directory and show it on the browser, so if the user uploads
# an image, that image is going to be show after the upload
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

def zipresults(filename, path,jobname):
    zipf = zipfile.ZipFile(jobname+".zip", 'w')
    zipdir('path', zipf)
    zipf.close()

def zipdir(path, ziph):
    # ziph is zipfile handle

    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))
    return ziph

def check_file_for_valid_input(filename):
    problems = ""
    open(filename)
    with open(filename, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
        for row in reader:
            line

    #   -- at least 4 rows (can't really do much with anything less
    #   -- no more than 20 rows (for now)
    return problems

# check to see:
#   -- that there is a string in the first position
#   -- more than 1 column of integers
def check_line_for_format(line):
    error=0
    col = line.split(line, '\t')
    if len(col)<3:
        error +=1

    if isinstance(col[0], basestring):
        pass
    else:
        error +=1

    for c in col[1:]:
        if isinstance(c,int):
            pass
        else:
            error +=1
    return error

def create_job():
    return uuid.uuid4()

def check_to_see_if_results_ready(jobname):
    os.path.isfile(jobname)


## checks sqlite table to see if its okay to start new job
## returns either "free", "busy" or errors
def check_to_see_if_processing_is_taking_place(jobname):
    con = None

    try:
        con = lite.connect(DATABASE_NAME)

        cur = con.cursor()
        cur.execute('SELECT status from tblProcessing where id = 1')

        data = cur.fetchone()

        return data

    except lite.Error, e:

        print "Error %s:" % e.args[0]
        return e.args[0]

    finally:
        if con:
            con.close()

def set_status_to_busy(jobname):
    con = None

    try:
        con = lite.connect(DATABASE_NAME)
        cur = con.cursor()
        cur.execute('update tblProcessing SET status=?, timestamp=?', ('busy','CURRENT_TIMESTAMP'))
        con.commit()

        return True

    except lite.Error, e:
        print "Error %s:" % e.args[0]
        return e.args[0]

    finally:
        if con:
            con.close()

def set_status_to_free(jobname):
    con = None
    try:
        con = lite.connect(DATABASE_NAME)
        cur = con.cursor()
        cur.execute('update tblProcessing SET status=?, timestamp=?', ('free','CURRENT_TIMESTAMP'))
        con.commit()
        return True
    except lite.Error, e:
        print "Error %s:" % e.args[0]
        return e.args[0]

    finally:
        if con:
            con.close()

def run_idss(filename, filepath, jobname):
    #set status to busy
    set_status_to_busy(jobname)
    cmd = ["idss-seriation", "--inputfile", filename, "--outputdirectory", filepath]
    p = subprocess.Popen(cmd, stdout = subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE)
    out,err = p.communicate()
    return out

if __name__ == '__main__':
    app.run()
