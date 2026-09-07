import sqlite3
from werkzeug.security import generate_password_hash

connection = sqlite3.connect('database.db')

schema = '''
    DROP TABLE IF EXISTS admins;
    DROP TABLE IF EXISTS notes;
    DROP TABLE IF EXISTS top_branches;
    
    CREATE TABLE admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    
    CREATE TABLE notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_name TEXT NOT NULL,
        author_course TEXT NOT NULL,
        title TEXT NOT NULL,
        subject TEXT NOT NULL,
        branch TEXT NOT NULL,
        semester INTEGER NOT NULL,
        description TEXT NOT NULL,
        file_link TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at DATE DEFAULT CURRENT_DATE
    );

    CREATE TABLE top_branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_name TEXT NOT NULL,
        note_count TEXT NOT NULL
    );
'''

connection.executescript(schema)
cur = connection.cursor()

# Create default Admin Account
admin_pass = generate_password_hash('admin123', method='pbkdf2:sha256')
cur.execute("INSERT INTO admins (email, password) VALUES (?, ?)", 
            ('admin@nie.edu', admin_pass))

# Seed initial top branches for home widget
cur.executemany("INSERT INTO top_branches (branch_name, note_count) VALUES (?, ?)", [
    ('Computer Science (BCA)', '12.4k'),
    ('B.COM Financial Mgmt', '10.8k'),
    ('BSC Electronics', '8.6k'),
    ('BBA Marketing', '7.3k')
])

connection.commit()
connection.close()
print("Database initialized successfully with all tables!")