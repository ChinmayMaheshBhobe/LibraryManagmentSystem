from flask_sqlalchemy import SQLAlchemy
from flask_security import UserMixin, RoleMixin
from datetime import datetime

# Initialize SQLAlchemy object
db = SQLAlchemy()


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)

    # Define relationship with User
    user = db.relationship('User', backref='ratings', lazy=True)

    # Define relationship with Book
    book = db.relationship('Book', backref='ratings', lazy=True)


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    # Hard copy or soft copy
    request_type = db.Column(db.String(10), nullable=False)
    # 0: Pending, 1: Accepted
    request_status = db.Column(db.Integer, default=None)
    request_date = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)
    request_days = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref='requests', lazy=True)

    book = db.relationship('Book', backref='requests', lazy=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey(
        'author.id'), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('type.id'), nullable=False)
    publish_year = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    content_url = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=5)
    remaining_quantity = db.Column(db.Integer, nullable=False, default=5)

    author = db.relationship('Author', backref='books', lazy=True)

    type = db.relationship('Type', backref='books', lazy=True)


def update_book_quantity():
    books = Book.query.all()
    for book in books:
        remaining_requests = Request.query \
            .filter_by(book_id=book.id) \
            .filter_by(request_status=1) \
            .filter_by(request_type='physicalShelf') \
            .count()
        book.remaining_quantity = max(0, book.quantity - remaining_requests)
    db.session.commit()


class Type(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    date_created = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=True)

class Librarian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)



class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)



class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class UserRoles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)  # Add phone field
    dob = db.Column(db.Date, nullable=False)  # Add dob field
    gender = db.Column(db.String(10), nullable=False)  # Add gender field
    active = db.Column(db.Boolean(), default=True)
    last_visited = db.Column(db.DateTime)

    def mark_visited(user):
        user.last_visited = datetime.utcnow()
        db.session.commit()

    # Define relationship with Role
    roles = db.relationship('Role', secondary='user_roles',
                            backref=db.backref('users', lazy='dynamic'))
