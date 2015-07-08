## IDSS-web: a flask-based webservice for the IDSS algorithim
## The goal of this project is to allow users to generate IDSS seriation results (basic frequency seriation as a start)
## using a web interface. The app must do some tracking of long running processes since it can take some time to get
## an IDSS result as we get larger #s of assemblages. We limit the number of assemblages so that the
## machine does not go into near-infinite processing. We want to log the activity (user info) and the datasets (input and output)
## Ultimately, the results should come in the form of an email with a link to the zipped results.
##
## This flask project is modeled after the example at: http://blog.miguelgrinberg.com/post/using-celery-with-flask
##
## Need to run: 1. celery worker -A IDSS-web.celery --loglevel=info (dont forget to stop and restart when debugging)
##              2. ./redis-server


## debug info can be found at: /var/www/uploads/idss-web.log

from flask import Flask, request, render_template, session, flash, redirect, \
    url_for, jsonify, send_from_directory, copy_current_request_context
from flask.ext.mail import Mail, Message
import os
from seriation import IDSS
import uuid
import csv
from pyparsing import *
import sqlite3 as lite
import sys
import zipfile
import re
import logging as log
import time
import random
from celery import Celery  # uses redis-server

DATABASE_NAME = './database/idssProcessing.sqlite'
UPLOAD_FOLDER = '/var/www/uploads/'
ALLOWED_EXTENSIONS = set(['txt'])
MAX_ASSEMBLAGES = 15

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Celery configuration
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

app.config['SECRET_KEY'] = 'top-secret!'

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'clipo@binghamton.edu'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)
mail = Mail(app)

log.basicConfig(filename=UPLOAD_FOLDER + "idss-web.log",level=log.DEBUG)

@celery.task(bind=True)
def run_idss(self,msg):
    (filename,filepath,jobname,email)=msg.split("|")

    with app.app_context():
        log.debug("now going to do long IDSS job via celery")

        message='processing...'
        self.update_state(state='PROGRESS', meta={'status': message})
        #set status to busy

        set_status_to_busy(jobname)

        seriation = IDSS()
        arguments={'inputfile': filename, 'outputdirectory': filepath, 'debug':0 }
        seriation.initialize(arguments)
        log.debug("seriation initialized with args. Now running IDSS for %s and job %s", (filename, jobname))
        (frequencyResults, continuityResults, exceptionList, statsMap) = seriation.seriate()

        message='done. zipping results....'
        self.update_state(state='PROGRESS',
                meta={'status': message})
        log.debug('Finished with IDSS processing for job %s', jobname)
        zipFileURL = zipresults(jobname)
        send_email(zipFileURL, email, jobname)
        message='done. emailing results....'
        self.update_state(state='PROGRESS', meta={'status': message})
        set_status_to_free(jobname)
        message='complete.'
        self.update_state(state='PROGRESS', meta={'status': message})

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
        data = {    'name' : name,
                    'email' : email,
                    'university' : university,
                    'filename': file.filename
                }
    else:
        return render_template('index.html', error=errors)


    if file and allowed_file(file.filename):

        session['name']=name
        session['university']=university
        jobname=create_job()
        session['jobname']=jobname
        log.debug('Created jobname: %s', jobname)
        filepath = UPLOAD_FOLDER+str(jobname)+"/"
        log.debug('Filepath is: %s', filepath)
        if not os.path.exists(filepath):
                os.makedirs(filepath)
        session['filepath']=filepath
        filename=(os.path.join(filepath, file.filename))
        log.debug('Filename is %s: ', filename)
        file.save(filename)
        problems = check_file_for_valid_input(filename)
        log.debug("Problems: %s", problems)
        session['filename']=filename
        session['filepath']=filepath
        session['email']=email
        if problems is not "":
            log.debug( 'Uh oh. Problems. Message: %s', problems)
            return render_template('index.html', error=problems, filename=filename, path=filepath, jobname=jobname)
        else:
            log.debug("now going to run idss task.")
            msg = str(filename)+"|"+str(filepath)+"|"+str(jobname)+"|"+str(email)
            task = run_idss.apply_async(args=[msg])
            log.debug("task id is: %s", task.id)
            return jsonify({}), 202, {'Location': url_for('taskstatus',
                                                  task_id=task.id)}

# This route is expecting a parameter containing the name
# of a file. Then it will locate that file on the upload
# directory and show it on the browser, so if the user uploads
# an image, that image is going to be show after the upload
@app.route('/uploads/<jobname>')
def uploaded_file(jobname):
    zipf=zipfile.ZipFile(jobname+".zip","w")
    zipdir="/var/www/uploads/"+jobname
    zipf.close()
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               zipf)

@app.route('/status/<task_id>')
def taskstatus(task_id):
    task = run_idss.AsyncResult(task_id)
    if task.state == 'PENDING':
        ## job did not start yet
        response = {
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'status': task.info.get('status', '')
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        # something went wrong in the background job
        response = {
            'status': str(task.info),  # this is the exception raised
        }
    return jsonify(response)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

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
    log.debug("Checking on file: %s for errors", filename)
    with open(filename, 'rb') as csvfile:
        log.debug("opening file: %s", filename)
        lines = file_len(filename)
        log.debug("number of lines in file: %d ", lines)
        if lines < 4:
            problems +=  " <li>Number of lines is < 4 which means there are only 2 lines plus header... not enough."
        if lines > MAX_ASSEMBLAGES:
            problems += " <li>Too many assemblages (Max is "+ MAX_ASSEMBLAGES + ")"
        ## skip the first line (header)
        next(csvfile)
        linenum = 1
        reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
        for row in reader:
            linenum +=1
            log.debug( "now on line: %s", linenum)
            problems += str(check_line_for_format(row))
            #   -- at least 4 rows (can't really do much with anything less
            #   -- no more than 20 rows (for now)
    log.debug("Problems encountered: %s ", problems)
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
    log.debug( "checking that there are enough columns. Number = %d", len(line))
    ## too few columns
    if len(line)<3:
        problems += " <li> Too few columns ", len(line), " is < 3. "
    ## check that first column is string
    log.debug( "Checking that the first column is a string.  First column: %s", str(line[0]))
    if isinstance(line[0], basestring):
        pass
    else:
        problems += " <li> First column entry is not a string. "

    ## check that that the other columns are integers
    log.debug( "checking the rest of the columns to see if they are all integers. ")
    for c in line[1:]:
        if isinstance(int(c),int):
            pass

        else:
            log.debug("data value is not an integer")
            problems += " <li> columns of data are not integers. "
    log.debug("Errors so far: %s ", problems)
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
        log.error("SQLlite Error: %s ", e.args[0])
        return e.args[0]

    finally:
        if con:
            con.close()

def set_status_to_busy(jobname):
    con = None
    try:
        con = lite.connect(DATABASE_NAME)
        cur = con.cursor()
        cur.execute('update tblProcessing SET status=?, last_update=?', ('busy','CURRENT_TIMESTAMP'))
        con.commit()
        return True
    except lite.Error, e:
        log.error("SQLlite Error: %s ", e.args[0])
        return e.args[0]

    finally:
        if con:
            con.close()

def set_status_to_free(jobname):
    con = None
    try:
        con = lite.connect(DATABASE_NAME)
        cur = con.cursor()
        cur.execute('update tblProcessing SET status=?, last_update=?', ('free','CURRENT_TIMESTAMP'))
        con.commit()
        return True
    except lite.Error, e:
        log.error("SQLlite Error: %s ", e.args[0])
        return e.args[0]

    finally:
        if con:
            con.close()

def zip_results(jobname):
    zipf=zipfile.ZipFile(jobname + ".zip", "w")
    zipdir= UPLOAD_FOLDER + jobname
    zipf.close()
    return "/uploads/"+ jobname + ".zip"

def send_email(zipfileURL, email, jobname):
    msgtxt = 'IDSS results from job: ' + str(jobname)
    msg = Message(msgtxt, recipients=[email]  )
    msg.body = 'Your seriation results are complete. You can download a compressed directory of the results here: ' + str(zipfileURL)
    """Background task to send an email with Flask-Mail."""
    with app.app_context():
        mail.send(msg)
        log.debug('Sending results of file %s to: %s', (zipfileURL,email))

def is_email_address_valid(email):
    """Validate the email address using a regex."""
    if not re.match("^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$", email):
        return False
    return True

if __name__ == '__main__':
    app.run()
