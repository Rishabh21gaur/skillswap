from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, BarterRequest, Review, ChatMessage
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-for-skillswap'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "skillswap.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize Database
with app.app_context():
    db.create_all()

# --- Auth Routes ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email address already exists')
            return redirect(url_for('signup'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.')
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Please check your login details and try again.')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Main Routes ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- Profile Routes ---
@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    reviews = Review.query.filter_by(reviewee_id=user.id).order_by(Review.timestamp.desc()).all()
    return render_template('profile.html', user=user, reviews=reviews)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio')
        current_user.skills_have = request.form.get('skills_have')
        current_user.skills_want = request.form.get('skills_want')
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile', user_id=current_user.id))
    return render_template('profile_edit.html')

# --- Search Routes ---
@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    users = []
    if query:
        users = User.query.filter(User.skills_have.ilike(f'%{query}%')).filter(User.id != current_user.id).all()
    else:
        if current_user.skills_want:
            wants = [w.strip() for w in current_user.skills_want.split(',') if w.strip()]
            filters = [User.skills_have.ilike(f'%{w}%') for w in wants]
            if filters:
                from sqlalchemy import or_
                users = User.query.filter(or_(*filters)).filter(User.id != current_user.id).all()
                
    return render_template('search.html', users=users, query=query)

# --- Request System Routes ---
@app.route('/requests')
@login_required
def barter_requests():
    incoming = BarterRequest.query.filter_by(receiver_id=current_user.id).order_by(BarterRequest.id.desc()).all()
    outgoing = BarterRequest.query.filter_by(sender_id=current_user.id).order_by(BarterRequest.id.desc()).all()
    return render_template('requests.html', incoming=incoming, outgoing=outgoing)

@app.route('/request/send/<int:user_id>', methods=['GET', 'POST'])
@login_required
def send_request(user_id):
    receiver = User.query.get_or_404(user_id)
    if request.method == 'POST':
        skill_offered = request.form.get('skill_offered')
        skill_requested = request.form.get('skill_requested')
        new_req = BarterRequest(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            skill_offered=skill_offered,
            skill_requested=skill_requested
        )
        db.session.add(new_req)
        db.session.commit()
        flash('Barter request sent successfully!', 'success')
        return redirect(url_for('barter_requests'))
    return render_template('request_form.html', receiver=receiver)

@app.route('/request/accept/<int:req_id>')
@login_required
def accept_request(req_id):
    req = BarterRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id and req.status == 'PENDING':
        req.status = 'ACCEPTED'
        db.session.commit()
        flash('Request accepted! You can now schedule a session.', 'success')
    return redirect(url_for('barter_requests'))

@app.route('/request/reject/<int:req_id>')
@login_required
def reject_request(req_id):
    req = BarterRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id and req.status == 'PENDING':
        req.status = 'REJECTED'
        db.session.commit()
        flash('Request rejected.')
    return redirect(url_for('barter_requests'))

# --- Scheduling & Reviews ---
@app.route('/request/schedule/<int:req_id>', methods=['GET', 'POST'])
@login_required
def schedule_session(req_id):
    req = BarterRequest.query.get_or_404(req_id)
    if current_user.id not in [req.sender_id, req.receiver_id] or req.status != 'ACCEPTED':
        flash('Unauthorized or invalid request.', 'error')
        return redirect(url_for('barter_requests'))
        
    if request.method == 'POST':
        dt_str = request.form.get('meeting_datetime')
        link = request.form.get('meeting_link')
        if dt_str:
            from datetime import datetime
            req.meeting_datetime = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
        req.meeting_link = link
        db.session.commit()
        flash('Session scheduled successfully!', 'success')
        return redirect(url_for('barter_requests'))
        
    return render_template('schedule_form.html', req=req)

@app.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def submit_review(req_id):
    req = BarterRequest.query.get_or_404(req_id)
    if current_user.id not in [req.sender_id, req.receiver_id] or req.status != 'ACCEPTED':
        return redirect(url_for('barter_requests'))
        
    existing = Review.query.filter_by(reviewer_id=current_user.id, request_id=req.id).first()
    if existing:
        flash('You have already reviewed this session.')
        return redirect(url_for('barter_requests'))
        
    reviewee_id = req.receiver_id if current_user.id == req.sender_id else req.sender_id
    reviewee = User.query.get(reviewee_id)
    
    if request.method == 'POST':
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')
        new_review = Review(
            reviewer_id=current_user.id,
            reviewee_id=reviewee_id,
            request_id=req.id,
            rating=rating,
            comment=comment
        )
        db.session.add(new_review)
        db.session.flush() 
        all_reviews = Review.query.filter_by(reviewee_id=reviewee_id).all()
        avg = sum(r.rating for r in all_reviews) / len(all_reviews) if all_reviews else 0.0
        reviewee.average_rating = avg
        db.session.commit()
        flash('Review submitted successfully!', 'success')
        return redirect(url_for('profile', user_id=reviewee_id))
        
    return render_template('review_form.html', req=req, reviewee=reviewee)

# --- Chat System Routes ---
@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    receiver = User.query.get_or_404(user_id)
    if request.method == 'POST':
        msg_text = request.form.get('message')
        if msg_text:
            new_msg = ChatMessage(
                sender_id=current_user.id,
                receiver_id=receiver.id,
                message=msg_text
            )
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('chat', user_id=receiver.id))
            
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == receiver.id)) |
        ((ChatMessage.sender_id == receiver.id) & (ChatMessage.receiver_id == current_user.id))
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return render_template('chat.html', receiver=receiver, messages=messages)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
