import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from pymongo import MongoClient
from datetime import datetime

# ========================================
# Initialize Flask App
# ========================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key'

# ========================================
# MongoDB Atlas Configuration
# ========================================
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)

db = client.get_database('taskmanager')
users_collection = db.users
tasks_collection = db.tasks

# ========================================
# Flask-Login Setup
# ========================================
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# ========================================
# Routes
# ========================================

@app.route('/')
@login_required
def dashboard():
    task_filter = request.args.get('filter', 'all')

    query = {'user_id': current_user.id}
    if task_filter == 'completed':
        query['status'] = 'Completed'
    elif task_filter == 'pending':
        query['status'] = 'Pending'

    tasks = list(tasks_collection.find(query))
    total_tasks = tasks_collection.count_documents({'user_id': current_user.id})
    completed_tasks = tasks_collection.count_documents({'user_id': current_user.id, 'status': 'Completed'})

    return render_template('dashboard.html',
                           tasks=tasks,
                           total_tasks=total_tasks,
                           completed_tasks=completed_tasks,
                           current_filter=task_filter)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if users_collection.find_one({'username': username}):
            flash('Username already exists!', 'danger')
            return redirect(url_for('signup'))

        users_collection.insert_one({
            'username': username,
            'password': generate_password_hash(password),
            'created_at': datetime.utcnow()
        })
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_data = users_collection.find_one({'username': username})
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))

        flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/task/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        task = {
            'user_id': current_user.id,
            'title': request.form['title'],
            'description': request.form['description'],
            'priority': request.form['priority'],
            'status': 'Pending',
            'assigned_to': request.form.get('assigned_to', ''),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        tasks_collection.insert_one(task)
        flash('Task added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('task_form.html')

@app.route('/task/edit/<task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = tasks_collection.find_one({'_id': ObjectId(task_id), 'user_id': current_user.id})
    if not task:
        flash('Task not found!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        tasks_collection.update_one(
            {'_id': ObjectId(task_id)},
            {'$set': {
                'title': request.form['title'],
                'description': request.form['description'],
                'priority': request.form['priority'],
                'assigned_to': request.form.get('assigned_to', ''),
                'updated_at': datetime.utcnow()
            }}
        )
        flash('Task updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('task_form.html', task=task)

@app.route('/task/complete/<task_id>')
@login_required
def complete_task(task_id):
    tasks_collection.update_one(
        {'_id': ObjectId(task_id), 'user_id': current_user.id},
        {'$set': {'status': 'Completed', 'updated_at': datetime.utcnow()}}
    )
    flash('Task marked as completed!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/task/delete/<task_id>')
@login_required
def delete_task(task_id):
    tasks_collection.delete_one({'_id': ObjectId(task_id), 'user_id': current_user.id})
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/team')
@login_required
def team():
    team_members = list(users_collection.find({'_id': {'$ne': ObjectId(current_user.id)}}))
    return render_template('team.html', team_members=team_members)

# ========================================
# Error Handlers
# ========================================
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

# ========================================
# Run the App
# ========================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
