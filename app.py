import os
from flask import Flask, render_template, request, redirect, url_for, g, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
from functools import wraps
import uuid

app = Flask(__name__)
app.secret_key = 'super_secret_production_key_change_this_later'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
os.makedirs(UPLOAD_FOLDER, exist_ok=True) 

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_name' not in session:
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- APIs FOR GAMIFICATION ---
@app.route('/api/view/<int:note_id>', methods=['POST'])
def add_view(note_id):
    db = get_db()
    db.execute("UPDATE notes SET views = views + 1 WHERE id = ?", (note_id,))
    db.commit()
    return jsonify({"status": "success"})

@app.route('/api/like/<int:note_id>', methods=['POST'])
def add_like(note_id):
    db = get_db()
    db.execute("UPDATE notes SET likes = likes + 1 WHERE id = ?", (note_id,))
    db.commit()
    likes = db.execute("SELECT likes FROM notes WHERE id = ?", (note_id,)).fetchone()['likes']
    return jsonify({"status": "success", "likes": likes})

# --- PUBLIC ROUTES ---
@app.route('/')
def dashboard():
    db = get_db()
    latest_notes = db.execute("SELECT * FROM notes WHERE status = 'approved' ORDER BY id DESC LIMIT 6").fetchall()
    top_branches = db.execute("SELECT * FROM top_branches ORDER BY id ASC LIMIT 5").fetchall()
    return render_template('dashboard.html', notes=latest_notes, popular=top_branches)

@app.route('/all_notes')
def all_notes():
    db = get_db()
    branch = request.args.get('branch', '')
    semester = request.args.get('semester', '')
    
    sql = "SELECT * FROM notes WHERE status = 'approved'"
    params = []
    
    if branch:
        sql += ' AND branch = ?'
        params.append(branch)
    if semester:
        sql += ' AND semester = ?'
        params.append(semester)
        
    sql += ' ORDER BY id DESC'
    
    notes = db.execute(sql, params).fetchall()
    branches = db.execute("SELECT * FROM course_branches ORDER BY name ASC").fetchall()
    
    return render_template('all_notes.html', notes=notes, selected_branch=branch, selected_semester=semester, branches=branches)

# --- STUDENT ROUTES ---
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        session['student_name'] = request.form['name']
        session['student_course'] = request.form['course']
        flash('Welcome to StudyShare!')
        return redirect(url_for('my_notes'))
    return render_template('student_login.html')

@app.route('/student_logout')
def student_logout():
    session.pop('student_name', None)
    session.pop('student_course', None)
    return redirect(url_for('dashboard'))

@app.route('/my_notes', methods=['GET', 'POST'])
@student_required
def my_notes():
    db = get_db()
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file and allowed_file(file.filename):
            unique_filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            file_link = '/' + file_path.replace('\\', '/')
            
            db.execute('''INSERT INTO notes (author_name, author_course, title, subject, branch, semester, description, file_link, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')''', 
                (session['student_name'], session['student_course'], request.form['title'], request.form['subject'], request.form['branch'], request.form['semester'], request.form['description'], file_link))
            db.commit()
            flash("Note uploaded successfully! Waiting for admin approval.")
            return redirect(url_for('my_notes'))

    my_notes = db.execute('SELECT * FROM notes WHERE author_name = ? ORDER BY id DESC', (session['student_name'],)).fetchall()
    branches = db.execute("SELECT * FROM course_branches ORDER BY name ASC").fetchall()
    return render_template('my_notes.html', notes=my_notes, branches=branches)

@app.route('/profile')
@student_required
def profile():
    db = get_db()
    stats = db.execute('SELECT COUNT(*) as total_notes, COALESCE(SUM(views), 0) as total_views, COALESCE(SUM(likes), 0) as total_likes FROM notes WHERE author_name = ? AND status = "approved"', (session['student_name'],)).fetchone()
    return render_template('profile.html', stats=stats)

# --- ADMIN ROUTES ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin = get_db().execute('SELECT * FROM admins WHERE email = ?', (request.form['email'],)).fetchone()
        if admin and check_password_hash(admin['password'], request.form['password']):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid Admin credentials.')
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('dashboard'))

@app.route('/admin', methods=['GET', 'POST']) 
@admin_required
def admin_dashboard():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. BULK ACTIONS
        if action == 'bulk_approve':
            note_ids = request.form.getlist('note_ids')
            for nid in note_ids:
                db.execute("UPDATE notes SET status = 'approved' WHERE id = ?", (nid,))
            db.commit()
            return redirect(url_for('admin_dashboard'))
        elif action == 'bulk_delete':
            note_ids = request.form.getlist('note_ids')
            for nid in note_ids:
                note = db.execute("SELECT file_link FROM notes WHERE id = ?", (nid,)).fetchone()
                if note and note['file_link']:
                    try: os.remove(note['file_link'].lstrip('/'))
                    except: pass
                db.execute("DELETE FROM notes WHERE id = ?", (nid,))
            db.commit()
            return redirect(url_for('admin_dashboard'))
        
        # 2. TOP BRANCHES WIDGET (INLINE EDITABLE)
        elif action == 'add_top_branch':
            db.execute("INSERT INTO top_branches (branch_name, note_count) VALUES (?, ?)", (request.form['branch_name'], request.form['note_count']))
            db.commit()
            return redirect(url_for('admin_dashboard'))
        elif action == 'edit_top_branch':
            db.execute("UPDATE top_branches SET branch_name = ?, note_count = ? WHERE id = ?", (request.form['branch_name'], request.form['note_count'], request.form['branch_id']))
            db.commit()
            return redirect(url_for('admin_dashboard'))
            
        # 3. COURSE BRANCHES MANAGEMENT
        elif action == 'add_course_branch':
            db.execute("INSERT OR IGNORE INTO course_branches (name) VALUES (?)", (request.form['branch_name'].strip().upper(),))
            db.commit()
            return redirect(url_for('admin_dashboard'))

        # 4. DIRECT FILE UPLOAD
        elif 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                unique_filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                file_link = '/' + file_path.replace('\\', '/')
                db.execute('''INSERT INTO notes (author_name, author_course, title, subject, branch, semester, description, file_link, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved')''', 
                    ("Teacher / Admin", "Faculty", request.form['title'], request.form['subject'], request.form['branch'], request.form['semester'], request.form['description'], file_link))
                db.commit()
                return redirect(url_for('admin_dashboard'))

    pending_notes = db.execute("SELECT * FROM notes WHERE status = 'pending' ORDER BY id DESC").fetchall()
    approved_notes = db.execute("SELECT * FROM notes WHERE status = 'approved' ORDER BY id DESC").fetchall()
    top_branches = db.execute("SELECT * FROM top_branches ORDER BY id ASC").fetchall()
    course_branches = db.execute("SELECT * FROM course_branches ORDER BY name ASC").fetchall()
    
    return render_template('admin.html', pending_notes=pending_notes, approved_notes=approved_notes, top_branches=top_branches, course_branches=course_branches)

@app.route('/admin/approve/<int:note_id>')
@admin_required
def approve_note(note_id):
    db = get_db()
    db.execute("UPDATE notes SET status = 'approved' WHERE id = ?", (note_id,))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:note_id>')
@admin_required
def delete_note(note_id):
    db = get_db()
    note = db.execute("SELECT file_link FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note and note['file_link']:
        try: os.remove(note['file_link'].lstrip('/'))
        except: pass
    db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_top_branch/<int:branch_id>')
@admin_required
def delete_top_branch(branch_id):
    db = get_db()
    db.execute("DELETE FROM top_branches WHERE id = ?", (branch_id,))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_course_branch/<int:branch_id>')
@admin_required
def delete_course_branch(branch_id):
    db = get_db()
    db.execute("DELETE FROM course_branches WHERE id = ?", (branch_id,))
    db.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)