from flask_mail import Message, Mail
import json
import os
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Api
from Db_Models import db, User, Librarian, Author, Book, Type, Request, UserRoles, Rating, update_book_quantity
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from redis_utils import get_redis_client


from flask_mail import Mail

# from forms import RegistrationForm, LoginForm

# Getting my (Class) api resources from resources.py
from resources import BookType, BooksResource, BooksByAuthorOrTypeResource, Section, BookUpdate, UserRoleCountResource, BookCountByTypeResource, TopBooksByRequests, getRequestCounts10Days, TopBooksByRatings, UserProfileResource, RequestStats, TopBooksByUser

from flask_cors import CORS
from requests import get
from urllib.parse import unquote  # Import unquote for decoding URL-encoded strings

project_path = '/Users/chinmaybhobe/Documents/Mad_2024_Final/backend'
# Create the Flask application instance
app = Flask(__name__)
CORS(app, supports_credentials=True)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)


# Configuration for SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(project_path, "database.db")}'
app.config['SECRET_KEY'] = 'thisisasecretkey'

app.config['SECURITY_USER_ID_ATTRIBUTE'] = 'id'

# Initialize SQLAlchemy object with the Flask application instance
db.init_app(app)

# Initialize Flask-RESTful's Api object
api = Api(app)

# Create a Redis client object
redis_client = get_redis_client()

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'chinmaybhobe@gmail.com'
app.config['MAIL_PASSWORD'] = 'bioe jolz hifs zaxz'
app.config['MAIL_DEFAULT_SENDER'] = 'chinmaybhobe@gmail.com'

mail = Mail(app)



# Add API resources to directly extract the resourse
api.add_resource(BooksResource, '/books', '/books/<int:book_id>')

# Register the API endpoint
api.add_resource(BooksByAuthorOrTypeResource, '/booksByAuthorOrTypeResource',
                 '/booksByAuthorOrTypeResource/author/<author_name>',
                 '/booksByAuthorOrTypeResource/type/<type_name>',
                 '/booksByAuthorOrTypeResource/title/<title>',
                 '/booksByAuthorOrTypeResource/<author_name>/<type_name>',
                 )

api.add_resource(BookType, '/book-type')

api.add_resource(Section, '/sections/<int:section_id>')

api.add_resource(BookUpdate, '/book-update/<int:book_id>')

# API for the statistics Page
# ADMIN
api.add_resource(UserRoleCountResource, '/user-role-count')
api.add_resource(BookCountByTypeResource, '/book-count-by-type')
api.add_resource(TopBooksByRequests, '/top-books-by-request')
api.add_resource(getRequestCounts10Days, '/get_request_counts_last_10_days')
api.add_resource(TopBooksByRatings, '/top-books-by-ratings')
# USER
api.add_resource(UserProfileResource, '/profile/<int:user_id>')
api.add_resource(RequestStats, '/request-stats/<int:user_id>')
api.add_resource(TopBooksByUser, '/top-books-by-user/<int:user_id>')


# ------------------------- PARTIAL INPUT SEARCH  ------------------------------------
@app.route('/suggestions/')
def suggestions():
    query = request.args.get('query', '')  # Get partial input from query parameters

    # Check if the query is present and not empty
    if query:
        # Check if the query suggestions are cached in Redis
        cached_data = redis_client.get(query)
        if cached_data:
            # If suggestions are found in the cache, return them directly
            return jsonify(json.loads(cached_data))

        # If suggestions are not found in the cache, execute database queries
        author_suggestions = Author.query.filter(Author.name.ilike(f'%{query}%')).all()
        section_suggestions = Type.query.filter(Type.name.ilike(f'%{query}%')).all()
        title_suggestions = Book.query.filter(Book.title.ilike(f'%{query}%')).all()

        # Construct suggestion objects
        author_data = [{'id': author.id, 'name': author.name} for author in author_suggestions]
        section_data = [{'id': section.id, 'name': section.name} for section in section_suggestions]
        title_data = [{'id': title.id, 'name': title.title} for title in title_suggestions]

        # Combine suggestion data into a single dictionary
        suggestions_data = {'authors': author_data, 'sections': section_data, 'titles': title_data}

        # Store suggestions data in Redis cache with an expiry time (e.g., 1 hour)
        redis_client.setex(query, 3600, json.dumps(suggestions_data))

        return jsonify(suggestions_data)
    else:
        return jsonify({'authors': [], 'sections': [], 'titles': []})


# -------------------------- TESTING FLASK MAIL -----------------------


@app.route('/send_email')
def send_email():
    # Create a Message object
    msg = Message('Hello', recipients=['chinmaybhobe@gmail.com'])
    msg.body = 'This is a test email'

    # Send the email
    mail.send(msg)

    return 'Email sent successfully!'


# -------------------------- USER ROLE CHANGE ------------------------


@app.route('/update_role', methods=['PUT'])
def update_role():
    data = request.json
    user_id = data.get('user_id')
    new_role_id = data.get('new_role_id')

    user_role = UserRoles.query.filter_by(user_id=user_id).first()
    if user_role:
        user_role.role_id = new_role_id
        db.session.commit()
        return jsonify({'message': 'Role updated successfully'}), 200
    else:
        return jsonify({'error': 'User role not found'}), 404

# ------------------------- VIEW BOOK -------------------------------


@app.route('/view-book/<int:book_id>', methods=['GET'])
def get_book(book_id):
    try:
        # Check if book data is cached
        cached_data = redis_client.get(f'book:{book_id}')
        if cached_data:
            # If cached data exists, return it
            return cached_data.decode('utf-8'), 200  # Decode bytes to string
        else:
            # Retrieve book details from the database
            book = Book.query.get(book_id)
            if book:
                # Create book data dictionary
                book_data = {
                    'id': book.id,
                    'title': book.title,
                    'isbn': book.isbn,
                    'author': book.author.name,  # Assuming author has a name attribute
                    'type': book.type.name,  # Assuming type has a name attribute
                    'publish_year': book.publish_year,
                    'image_url': book.image_url,
                    'content_url': book.content_url
                    # Add more fields as needed
                }
                # Cache book data in Redis with a TTL of 60 seconds (for example)
                redis_client.setex(f'book:{book_id}', 3600, json.dumps(
                    book_data))  # Serialize to JSON string
                # Return book data to the client
                return jsonify(book_data), 200
            else:
                return jsonify({'error': 'Book not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------------- SUBMIT-RATINGS ---------------------------
@app.route('/user-ratings', methods=['POST'])
def get_ratings():
    data = request.json
    user_id = data['user_id']
    book_id = data['book_id']
    new_rating_value = data['rating']

    # Check if a rating already exists for the user and book
    existing_rating = Rating.query.filter_by(
        user_id=user_id, book_id=book_id).first()

    if existing_rating:
        # Update the existing rating
        existing_rating.rating = new_rating_value
    else:
        # Create a new rating
        new_rating = Rating(
            user_id=user_id,
            book_id=book_id,
            rating=new_rating_value
        )
        db.session.add(new_rating)

    db.session.commit()
    return jsonify({'message': 'Rating submitted successfully'})


# ------------------------- ADMIN RESPONSE --------------------------


@app.route('/admin-requests/<int:request_id>/accept', methods=['PUT'])
def accept_request(request_id):
    request = Request.query.get(request_id)
    if request:
        request.request_status = 1
        db.session.commit()
        update_book_quantity()
        return jsonify({'message': 'Request accepted successfully'}), 200
    else:
        return jsonify({'message': 'Request not found'}), 404


@app.route('/admin-requests/<int:request_id>/reject', methods=['PUT'])
def reject_request(request_id):
    request = Request.query.get(request_id)
    if request:
        request.request_status = 0  # Set request status to 0 (rejected)
        db.session.commit()
        return jsonify({'message': 'Request rejected successfully'}), 200
    else:
        return jsonify({'message': 'Request not found'}), 404


# ------------------------- ADMIN REQUEST --------------------------
@app.route('/admin-requests', methods=['GET'])
def get_admin_requests():
    all_requests = Request.query.all()
    serialized_requests = []
    for request in all_requests:
        # Fetch the book details based on the book_id
        book = Book.query.get(request.book_id)
        if book:
            author = Author.query.get(book.author_id)
            user = User.query.get(request.user_id)

            # Include book title in the serialized data
            serialized_request = {
                'id': request.id,
                'user_name': user.username,
                'author_name': author.name,
                'book_id': request.book_id,
                'book_title': book.title,  # Include book title
                'request_type': request.request_type,
                'request_days': request.request_days,
                'request_status': request.request_status,
                'image_url': book.image_url
            }
            serialized_requests.append(serialized_request)

    # Return the serialized requests data as a response
    return jsonify(serialized_requests), 200


# ------------------------- REQUEST ACCESS USER --------------------

@app.route('/return-book/<int:request_id>', methods=['PUT'])
def return_book(request_id):
    request = Request.query.get(request_id)
    if request:
        request.request_status = -1  # Update request status to -1 (returned)
        db.session.commit()
        update_book_quantity()

        return jsonify({'message': 'Book returned successfully'}), 200
    else:
        return jsonify({'message': 'Request not found'}), 404


@app.route('/pending-requests/<int:user_id>', methods=['GET'])
def get_user_requests(user_id):
    # Query the database to fetch requests for the provided user_id with null status
    user_requests = Request.query.filter_by(
        user_id=user_id).all()

    # Query the UserRoles table to get the user_role_id
    user_roles = UserRoles.query.filter_by(user_id=user_id).first()
    user_role_id = user_roles.role_id if user_roles else None

    serialized_requests = []
    for request in user_requests:
        # Fetch the book details based on the book_id
        book = Book.query.get(request.book_id)
        if book:
            # Include book title in the serialized data
            serialized_request = {
                'id': request.id,
                'book_id': request.book_id,
                'book_title': book.title,  # Include book title
                'request_type': request.request_type,
                'request_days': request.request_days,
                'request_status': request.request_status,
                'image_url': book.image_url,
                'user_role_id': user_role_id,
                'request_date': request.request_date
            }
            serialized_requests.append(serialized_request)

    # Return the serialized requests data as a response
    return jsonify(serialized_requests), 200


# ------------------------- USER REQUEST --------------------------------


@app.route('/send-request', methods=['POST'])
def send_request():
    data = request.json
    new_request = Request(
        user_id=data['user_id'],
        book_id=data['book_id'],
        request_type=data['request_type'],
        request_days=data['request_days'],
        request_date=datetime.utcnow()
    )
    db.session.add(new_request)
    db.session.commit()
    return jsonify({'message': 'Request sent successfully'})


# ------------------------ DELETE SECTION -------------------------------


@app.route('/sections/<int:section_id>', methods=['DELETE'])
@jwt_required()
def delete_section(section_id):
    token = request.headers.get('Authorization').split()[1]
    decoded_token = decode_token(token)
    print('Decoded JWT payload:', decoded_token)
    current_user = get_jwt_identity()
    print('Current user:', current_user)

    if current_user != 1 and decoded_token['username'] != 'admin1':
        return jsonify({'error': 'Unauthorized. Only admin1 can delete sections.'}), 401
    
    # Find the section by ID
    section = Type.query.get(section_id)

    if not section:
        return jsonify({'error': 'Section not found'}), 404

    try:
        # Delete all books associated with the section
        Book.query.filter_by(type_id=section_id).delete()

        # Delete the section itself
        db.session.delete(section)
        db.session.commit()

        return jsonify({'message': 'Section and associated books deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete section and associated books', 'details': str(e)}), 500

# ------------------------- SECTION CREATE -----------------------------
@app.route('/section-form', methods=['POST'])
@jwt_required()
def create_section():
    token = request.headers.get('Authorization').split()[1]
    decoded_token = decode_token(token)
    print('Decoded JWT payload:', decoded_token)
    current_user = get_jwt_identity()
    print('Current user:', current_user)

    if current_user != 1 and decoded_token['username'] != 'admin1':
        return jsonify({'error': 'Unauthorized. Only admin1 can create books.'}), 401

    
    data = request.json
    name = data.get('name')
    description = data.get('description')

    if not name or not description:
        return jsonify({'error': 'Name and description are required'}), 400

    # Create a new section entry
    section = Type(name=name, description=description)
    db.session.add(section)
    db.session.commit()

    return jsonify({'message': 'Section created successfully'}), 201


# -------------------------- BOOK CREATE -------------------------------



@app.route('/book-create', methods=['POST'])
@jwt_required()
def create_book():
    try:
        token = request.headers.get('Authorization').split()[1]
        decoded_token = decode_token(token)
        print('Decoded JWT payload:', decoded_token)
        current_user = get_jwt_identity()
        print('Current user:', current_user)

        if current_user != 1 and decoded_token['username'] != 'admin1':
            return jsonify({'error': 'Unauthorized. Only admin1 can create books.'}), 401



        data = request.json
        title = data.get('title')
        isbn = data.get('isbn')
        author_name = data.get('author_name')
        publish_year = data.get('publish_year')
        image_url = data.get('image_url')
        content_url = data.get('content_url')
        type_id = data.get('type_id')

        # Check if all required fields are provided
        if not title or not isbn or not author_name or not publish_year or not type_id:
            return jsonify({'error': 'Please provide all required fields (title, isbn, author_name, publish_year, type_id)'}), 400

        # Check if author already exists
        author = Author.query.filter_by(name=author_name).first()
        if not author:
            # If author does not exist, create a new author
            author = Author(name=author_name)
            db.session.add(author)
            db.session.commit()

        # Create a new book entry
        book = Book(
            title=title,
            isbn=isbn,
            author_id=author.id,
            publish_year=publish_year,
            image_url=image_url,
            content_url=content_url,
            type_id=type_id
        )
        db.session.add(book)
        db.session.commit()

        return jsonify({'message': 'Book created successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# -------------------------- ADMIN-LOGIN -------------------------------

@app.route('/admin-login', methods=['POST'])
def login_admin():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    print(data)

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    librarian = Librarian.query.filter_by(username=username).first()

    if not librarian or librarian.password != password:
        return jsonify({'message': 'Invalid username or password'}), 401

    # Generate JWT token
    access_token = create_access_token(identity=librarian.id, additional_claims={'username': librarian.username})
    return jsonify({'access_token': access_token}), 200

# -------------------------- LOGIN-USER -------------------------------
@app.route('/user-login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid username or password'}), 401

    user.mark_visited()

    # Generate JWT token
    identity = {'user_id': user.id, 'username': user.username}
    access_token = create_access_token(identity=identity)
    return jsonify({'access_token': access_token}), 200


# ------------------------- REGISTER USER ------------------------------
# Define the route for user registration
@app.route('/user-register', methods=['POST'])
def register_user():
    try:
        # Extract user registration data from the request
        user_data = request.json
        print("Received user data:", user_data)

        # Access individual fields from the user data dictionary
        username = user_data.get('username')
        password = user_data.get('password')
        email = user_data.get('email')
        phone = user_data.get('phone')
        dob_str = user_data.get('dob')
        gender = user_data.get('gender')

        # Convert dob string to Python date object
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()

        # Check if the username or email already exists in the database
        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'message': 'Username already exists!'}), 400
        if existing_email:
            return jsonify({'message': 'Email already exists!'}), 400

        # Hash the password using bcrypt
        hashed_password = bcrypt.generate_password_hash(
            password).decode('utf-8')

        # Create a new user object
        new_user = User(username=username, password=hashed_password,
                        email=email, phone=phone, dob=dob, gender=gender)

        # Add the new user to the session
        db.session.add(new_user)

        # Commit the session to the database
        db.session.commit()

        new_user.mark_visited()

        # Assuming registration is successful
        # Generate JWT token
        identity = {'user_id': new_user.id, 'username': new_user.username}
        access_token = create_access_token(identity=identity)

        # Populate UserRoles table with default values
        new_user_role = UserRoles(user_id=new_user.id, role_id=1)
        db.session.add(new_user_role)
        db.session.commit()

        return jsonify({'message': 'Registration successful!', 'access_token': access_token}), 201
    except ValueError:
        return jsonify({'message': 'Invalid date format for date of birth! Use YYYY-MM-DD.'}), 400
    except Exception as e:
        # Rollback the session in case of an exception
        db.session.rollback()
        print("Error occurred while registering user:", e)
        return jsonify({'message': 'Error occurred while registering user'}), 500



if __name__ == '__main__':
    with app.app_context():
        # Create SQLite database tables based on defined models
        db.create_all()

    # Run the Flask application
    app.run(debug=True)
