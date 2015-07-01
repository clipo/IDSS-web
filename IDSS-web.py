
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
import re

DATABASE_NAME = './database/idssProcessing.sqlite'
UPLOAD_FOLDER = '/var/www/uploads/'
ALLOWED_EXTENSIONS = set(['txt'])
MAX_ASSEMBLAGES = 15

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
    name = request.form['name']
    university= request.form['university']
    email = request.form['email']
    errors = ""
    if not name or not email or not university:
        errors = "<li>Please enter all the fields."

    if not is_email_address_valid(email):
        errors +=  "<li>Please enter a valid email address"

    if not errors:
        # If there are no errors, create a dictionary containing all the entered
        data = {'name' : name,
                    'email' : email,
                    'university' : university
                    }
    else:
        return render_template('index.html', error=errors)

    if file and allowed_file(file.filename):
        jobname=create_job()
        print jobname
        filepath = UPLOAD_FOLDER+str(jobname)+"/"
        print filepath
        if not os.path.exists(filepath):
                os.makedirs(filepath)
        filename=(os.path.join(filepath, file.filename))
        print filename
        file.save(filename)
        problems = check_file_for_valid_input(filename)
        print "problems: ", problems
        if problems is not "":
            print "Uh oh. Problems."
            return render_template('index.html', error=problems, filename=filename, path=filepath, jobname=jobname)
        else:
            ##run_idss(filename,filepath,jobname)
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
    print "Checking on file: ", filename, " for errors."
    with open(filename, 'rb') as csvfile:
        print "opening file: ", filename
        lines = file_len(filename)
        print "number of lines in file: ", lines
        if lines < 4:
            problems +=  " <li>Number of lines is < 4 which means there are only 2 lines plus header... not enough."
        if lines > MAX_ASSEMBLAGES:
            problems += " <li>Too many assemblages (Max is "+ MAX_ASSEMBLAGES + ")"
        print "No problem with numbers of lines"
        ## skip the first line (header)
        next(csvfile)
        linenum = 1
        print "skipped first line (header). "
        reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
        for row in reader:
            linenum +=1
            print "now on line ", linenum
            problems += str(check_line_for_format(row))
            #   -- at least 4 rows (can't really do much with anything less
            #   -- no more than 20 rows (for now)
    print "Problems encountered: ", problems
    return problems

def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i + 1
# check to see:
#   -- that there is a string in the first position
#   -- more than 1 column of integers
def check_line_for_format(line):
    problems = ""
    print "checking that there are enough columns. Number = ", len(line)
    ## too few columns
    if len(line)<3:
        problems += " <li> Too few columns ", len(line), " is < 3. "


    ## check that first column is string
    print "checking that the first column is a string.  First column: ", line[0]
    if isinstance(line[0], basestring):
        pass
    else:
        problems += " <li> First column entry is not a string. "


    ## check that that the other columns are integers
    print "checking the rest of the columns to see if they are all integers. "
    for c in line[1:]:
        if isinstance(int(c),int):
            print c, " is an integer"
            pass

        else:
            print c, " is not an integer"
            problems += " <li> columns of data are not integers. "
    print "Errors so far: ", problems
    return problems

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

def is_email_address_valid(email):
    """Validate the email address using a regex."""
    if not re.match("^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$", email):
        return False
    return True

if __name__ == '__main__':
    app.run()
