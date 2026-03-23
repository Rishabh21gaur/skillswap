from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    skills_have = db.Column(db.Text, nullable=True) # Comma separated
    skills_want = db.Column(db.Text, nullable=True) # Comma separated
    average_rating = db.Column(db.Float, default=0.0)
    
    # Relationships
    reviews_received = db.relationship('Review', foreign_keys='Review.reviewee_id', backref='reviewee', lazy=True)

class BarterRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    skill_offered = db.Column(db.String(150), nullable=False)
    skill_requested = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(50), default='PENDING') # PENDING, ACCEPTED, REJECTED
    meeting_datetime = db.Column(db.DateTime, nullable=True)
    meeting_link = db.Column(db.String(255), nullable=True)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='requests_sent', lazy=True)
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='requests_received', lazy=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('barter_request.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1-5
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship('User', foreign_keys=[reviewer_id], lazy=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='messages_sent', lazy=True)
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='messages_received', lazy=True)
