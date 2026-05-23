from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class Book(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    title          = db.Column(db.String(100), nullable=False)
    author         = db.Column(db.String(100), nullable=False)
    published_year = db.Column(db.Integer, nullable=False)
    isbn           = db.Column(db.String(13), unique=True, nullable=False)
    available      = db.Column(db.Boolean, default=True)
    category       = db.Column(db.String(50), nullable=True)
    status         = db.Column(db.String(20), default='Unread')
    description    = db.Column(db.Text, nullable=True)
    notes          = db.Column(db.Text, nullable=True)
    archived       = db.Column(db.Boolean, default=False)
    format         = db.Column(db.String(20), nullable=False)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating         = db.Column(db.Integer, nullable=True)
    date_added     = db.Column(db.DateTime, default=datetime.utcnow)
    total_pages    = db.Column(db.Integer, nullable=True)
    current_page   = db.Column(db.Integer, default=0)

    owner = db.relationship('User', backref='books', lazy=True)

    @property
    def read_pct(self):
        if self.total_pages and self.total_pages > 0:
            return min(100, round((self.current_page or 0) / self.total_pages * 100))
        return 0


class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(50), nullable=False)
    email         = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Borrow(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id     = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime, nullable=True)
    returned    = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='borrows', lazy=True)
    book = db.relationship('Book', backref='borrows', lazy=True)


class Favorite(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user    = db.relationship('User', backref='favorites', lazy=True)
    book    = db.relationship('Book', backref='favorites', lazy=True)


class ReadingGoal(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    year       = db.Column(db.Integer, nullable=False)
    goal_count = db.Column(db.Integer, nullable=False, default=12)
    user       = db.relationship('User', backref='reading_goals', lazy=True)
