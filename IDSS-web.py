
from flask import render_template
from flask import Flask, request, redirect, url_for
import os.path
import os
from seriation import IDSS
import uuid
import csv
from pyparsing import *
import sqlite3 as lite
import sys

DATABASE_NAME = '/database/idssProcessing.sqlite'
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
            jobname=create_job()
            filepath = app.config['UPLOAD_FOLDER']+jobname+"/"
            filename=(os.path.join(filepath, file.filename))
            file.save(filename)
            problems = check_file_for_valid_input(filename)
            if problems is not None:
                render_template('/index.html', problems=problems)
            else:
                return redirect(url_for('/processing',
                                    filename=filename))
@app.route('/processing')
def check_to_see_if_done()


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

if __name__ == '__main__':
    app.run()
