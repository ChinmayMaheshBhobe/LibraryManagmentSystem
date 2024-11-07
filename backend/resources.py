from Db_Models import Book, Author, Type, db
from urllib.parse import unquote
from flask_restful import Resource, abort
from flask_restful import Resource
from Db_Models import Book, Author, Type, UserRoles, Role, update_book_quantity, User
from flask import abort, request, jsonify
import json
from sqlalchemy import text
from datetime import datetime
import traceback
from redis_utils import get_redis_client
from flask_jwt_extended import decode_token



# ------------------- USER STATISTICS -----------------------------
class UserProfileResource(Resource):
    def get(self, user_id):
        # Use raw SQL query to fetch user data along with associated roles
        query = text("""
            SELECT u.id, u.username, u.email, u.phone, u.gender, u.active, r.id AS role_id, r.name AS role_name
            FROM user u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN role r ON ur.role_id = r.id
            WHERE u.id = :user_id
        """)
        result = db.session.execute(query, {'user_id': user_id}).fetchall()
        user_profile = [{'id': row[0], 'username': row[1], 'email': row[2],
                         'phone': row[3], 'gender': row[4], 'active': row[5], 'role_id': row[6], 'role_name': row[7]} for row in result]

        return jsonify({'user_profile': user_profile})


class RequestStats(Resource):
    def get(self, user_id):
        # Raw SQL query to fetch request statistics
        query = text("""
            SELECT DATE(request_date) AS request_date,
                   SUM(CASE WHEN request_type = 'physicalShelf' THEN 1 ELSE 0 END) AS physicalShelf_count,
                   SUM(CASE WHEN request_type = 'eShelf' THEN 1 ELSE 0 END) AS eShelf_count
            FROM request
            WHERE user_id = :user_id
            AND request_date >= DATE('now', '-10 days')
            GROUP BY DATE(request_date)
            ORDER BY request_date
        """)

        # Execute the query
        result = db.session.execute(query, {'user_id': user_id})

        # Convert the result to a list of dictionaries
        User_request_counts_last_10_days = [
            {
                # Accessing the first element of the tuple (request_date)
                'date': row[0],
                # Accessing the second element of the tuple (physicalShelf_count)
                'physicalShelf_count': row[1],
                # Accessing the third element of the tuple (eShelf_count)
                'eShelf_count': row[2]
            }
            for row in result
        ]

        return jsonify({'request_type': User_request_counts_last_10_days})


class TopBooksByUser(Resource):
    def get(self, user_id):
        # Construct SQL query using text format
        sql_query = text("""
            SELECT book.title, rating.rating
            FROM rating
            JOIN book ON rating.book_id = book.id
            WHERE rating.user_id = :user_id
            ORDER BY rating.rating DESC
            LIMIT 10
        """)

        # Execute the SQL query
        top_books = db.session.execute(sql_query, {'user_id': user_id})

        # Extract book details for the top rated books
        top_books_details = [{'title': row[0], 'rating': row[1]}
                             for row in top_books]

        return jsonify({'top_books_by_user': top_books_details})

# ------------------- ADMIN STATISTICS ----------------------------


class UserRoleCountResource(Resource):
    def get(self):
        # Query the database to get the count of users for each role_id
        user_role_counts = db.session.query(UserRoles.role_id, Role.name, db.func.count(
            UserRoles.user_id)).join(Role).group_by(UserRoles.role_id).all()

        # Prepare response data
        role_counts = {}
        for role_id, role_name, count in user_role_counts:
            role_counts[role_name] = count

        return jsonify(role_counts)


class BookCountByTypeResource(Resource):
    def get(self):
        # SQL query to get the count of books for each type
        query = text("""
            SELECT t.name AS type_name, COUNT(b.id) AS book_count
            FROM type AS t
            JOIN book AS b ON t.id = b.type_id
            GROUP BY t.name
            ORDER BY COUNT(b.id) DESC
        """)
        result = db.session.execute(query)
        data = [{'type_name': row[0], 'book_count': row[1]} for row in result]

        return jsonify({'data': data})


class TopBooksByRequests(Resource):
    def get(self):
        # SQL query to get the top 10 books with the highest number of requests
        query = text("""
            SELECT b.title AS book_title, COUNT(r.id) AS request_count
            FROM book AS b
            JOIN request AS r ON b.id = r.book_id
            GROUP BY b.title
            ORDER BY request_count DESC
            LIMIT 10
        """)
        result = db.session.execute(query)
        top_books_data = [{'book_title': row[0],
                           'request_count': row[1]} for row in result]

        return jsonify({'top_books': top_books_data})


class getRequestCounts10Days(Resource):
    def get(self):
        query = text("""
        SELECT DATE(request_date) AS request_date,
               SUM(CASE WHEN request_type = 'physicalShelf' THEN 1 ELSE 0 END) AS physicalShelf_count,
               SUM(CASE WHEN request_type = 'eShelf' THEN 1 ELSE 0 END) AS eShelf_count
        FROM request
        WHERE request_date >= DATE('now', '-10 days')
        GROUP BY DATE(request_date)
        ORDER BY request_date
        """)
        result = db.session.execute(query)

        # Convert the result to a list of dictionaries
        request_counts_last_10_days = [
            {
                # Accessing the first element of the tuple (request_date)
                'date': row[0],
                # Accessing the second element of the tuple (physicalShelf_count)
                'physicalShelf_count': row[1],
                # Accessing the third element of the tuple (eShelf_count)
                'eShelf_count': row[2]
            }
            for row in result
        ]

        return jsonify({'request_type': request_counts_last_10_days})


class TopBooksByRatings(Resource):
    def get(self):
        # SQL query to calculate the average rating of each book
        avg_ratings_query = text("""
            SELECT r.book_id, AVG(r.rating) AS avg_rating
            FROM rating r
            GROUP BY r.book_id
        """)

        # SQL query to get the top 10 books with the highest average ratings
        top_books_query = text("""
            SELECT b.id, b.title, avg_ratings.avg_rating
            FROM book b
            JOIN (
                {}
            ) AS avg_ratings ON b.id = avg_ratings.book_id
            ORDER BY avg_ratings.avg_rating DESC
            LIMIT 10
        """.format(avg_ratings_query))

        # Execute the raw SQL queries
        avg_ratings_results = db.session.execute(avg_ratings_query).fetchall()
        top_books_results = db.session.execute(top_books_query).fetchall()

        # Format the result as a list of dictionaries
        top_books_data = [
            {'book_id': book_id, 'title': title, 'avg_rating': avg_rating}
            for book_id, title, avg_rating in top_books_results
        ]

        return jsonify({'top_books_by_ratings': top_books_data})

# ------------------ UPDATE BOOK ----------------------------------


class BookUpdate(Resource):
    def put(self, book_id):
        try:
            token = request.headers.get('Authorization').split()[1]
            decoded_token = decode_token(token)
            current_user_id = decoded_token.get('sub')
            current_user_name = decoded_token.get('username')
            print(current_user_id,current_user_name)

            # Ensure that the user is an admin
            if current_user_id != 1 or current_user_name != 'admin1':
                return jsonify({'error': 'Unauthorized. Only admin1 can delete books.'}), 401

            data = request.json
            title = data.get('title')
            isbn = data.get('isbn')
            authorName = data.get('author')
            existingAuthorName = data.get('existingAuthorName')  
            publishYear = data.get('publishYear')
            imageUrl = data.get('imageUrl')
            quantity = data.get('quantity')

            # Find the book in the database
            book = Book.query.get(book_id)
            if not book:
                return {'message': 'Book not found'}, 404

            # Find the author in the database by name
            existing_author = Author.query.filter_by(name=existingAuthorName).first()
            if not existing_author:
                return {'message': 'Author not found'}, 404
      
            existing_author.name = authorName



            # Update the book with the new data
            book.title = title
            book.isbn = isbn
            book.author_id = existing_author.id  
            book.publish_year = publishYear
            book.imageUrl = imageUrl
            book.quantity = quantity

            db.session.commit()

            update_book_quantity()

            return {'message': 'Book updated successfully'}, 200
        except Exception as e:
            # Log the exception
            traceback.print_exc()
            # Return a generic error message
            return {'message': 'Internal server error'}, 500

# ------------------ UPDATE SECTION (TYPE)--------------------------


class Section(Resource):
    def put(self, section_id):
        token = request.headers.get('Authorization').split()[1]
        decoded_token = decode_token(token)
        current_user_id = decoded_token.get('sub')
        current_user_name = decoded_token.get('username')
        print(current_user_id,current_user_name)

        # Ensure that the user is an admin
        if current_user_id != 1 or current_user_name != 'admin1':
            return jsonify({'error': 'Unauthorized. Only admin1 can delete books.'}), 401


        data = request.json
        name = data.get('name')
        description = data.get('description')

        # Find the section in the database
        section = Type.query.get(section_id)
        if not section:
            return {'message': 'Section not found'}, 404

        # Update the section with the new data
        section.name = name
        section.description = description
        db.session.commit()  # Assuming you're using SQLAlchemy

        return {'message': 'Section updated successfully'}, 200


class BookType(Resource):
    def get(self):
        types = Type.query.all()
        type_list = [{'id': type.id, 'name': type.name,
                      'description': type.description} for type in types]
        return {'types': type_list}, 200


class BooksResource(Resource):
    def get(self):
        # Retrieve type_id from the request query parameters
        type_id = request.args.get('type_id')

        # Filter books by type_id if provided
        if type_id:
            books = Book.query.filter_by(type_id=type_id).all()
        else:
            # Retrieve all books if type_id is not provided
            books = Book.query.all()

        # Serialize the data to JSON
        books_json = [{'id': book.id, 'title': book.title, 'isbn': book.isbn, 'quantity': book.quantity, 'remaining_quantity': book.remaining_quantity,
                       'author_id': book.author_id, 'author_name': book.author.name, 'type_id': book.type_id, 'type_name': book.type.name, 'image_url': book.image_url, 'publish_year': book.publish_year} for book in books]

        return {'books': books_json}, 200
    
    def delete(self, book_id):
        token = request.headers.get('Authorization').split()[1]
        decoded_token = decode_token(token)
        current_user_id = decoded_token.get('sub')
        current_user_name = decoded_token.get('username')
        print(current_user_id,current_user_name)

        # Ensure that the user is an admin
        if current_user_id != 1 or current_user_name != 'admin1':
            return jsonify({'error': 'Unauthorized. Only admin1 can delete books.'}), 401


        # Retrieve the book by its ID
        book = Book.query.get(book_id)
        if not book:
            return {'error': 'Book not found'}, 404

        # Delete the book
        db.session.delete(book)
        db.session.commit()

        return {'message': 'Book deleted successfully'}, 200


class BooksByAuthorNameResource(Resource):
    def get(self, author_name):
        # Query the database to filter books by author name
        author = Author.query.filter_by(name=author_name).first()
        if not author:
            abort(404, message="Author not found")

        books = Book.query.filter_by(author_id=author.id).all()

        # Serialize the data to JSON
        books_json = [{'id': book.id, 'title': book.title,
                       'isbn': book.isbn, 'author_name': book.author.name, 'image_url': book.image_url} for book in books]

        return {'books': books_json}, 200


class BooksByTypeNameResource(Resource):
    def get(self, type_name):
        book_type = Type.query.filter_by(name=type_name).first()
        if not book_type:
            abort(404, message="Book type not found")
        books = Book.query.filter_by(type_id=book_type.id).all()

        # Serialize the data to JSON
        books_json = [{'id': book.id, 'title': book.title,
                       'isbn': book.isbn, 'author_name': book.author.name, 'image_url': book.image_url, 'book_type': book.type.name} for book in books]

        return {'books': books_json}, 200



redis_client = get_redis_client()

class BooksByAuthorOrTypeResource(Resource):
    def get(self, author_name=None, type_name=None, title=None):
        # Decode the author's name and type from URL encoding
        cache_key = f"{author_name}_{type_name}_{title}"
        cached_result = redis_client.get(cache_key)
        if cached_result:
            # If cached result exists, return it
            return json.loads(cached_result), 200

        
        decoded_author_name = unquote(author_name) if author_name else None
        decoded_type_name = unquote(type_name) if type_name else None
        decoded_title = unquote(title) if title else None

        # Query the database to filter books by author name, type name, and/or title
        books_query = Book.query

        if decoded_author_name and decoded_type_name:
            author = Author.query.filter_by(name=decoded_author_name).first()
            book_type = Type.query.filter_by(name=decoded_type_name).first()

            if not author or not book_type:
                abort(404)

            # Filter by author, type, and title if provided
            if decoded_title:
                books = books_query.filter_by(author_id=author.id, type_id=book_type.id, title=decoded_title).all()
            else:
                books = books_query.filter_by(author_id=author.id, type_id=book_type.id).all()

        elif decoded_author_name:
            author = Author.query.filter_by(name=decoded_author_name).first()

            if not author:
                abort(404)

            # Filter by author and title if provided
            if decoded_title:
                books = books_query.filter_by(author_id=author.id, title=decoded_title).all()
            else:
                books = books_query.filter_by(author_id=author.id).all()

        elif decoded_type_name:
            book_type = Type.query.filter_by(name=decoded_type_name).first()

            if not book_type:
                abort(404)

            # Filter by type and title if provided
            if decoded_title:
                books = books_query.filter_by(type_id=book_type.id, title=decoded_title).all()
            else:
                books = books_query.filter_by(type_id=book_type.id).all()

        elif decoded_title:
            # Filter by title only
            books = books_query.filter_by(title=decoded_title).all()

        else:
            # If no search criteria provided, return all books
            books = books_query.all()

        # Serialize the data to JSON
        books_json = [{'id': book.id, 'title': book.title,
                       'isbn': book.isbn, 'author_name': book.author.name, 'remaining': book.remaining_quantity,
                       'image_url': book.image_url, 'book_type': book.type.name, 'publish_year': book.publish_year}
                      for book in books]
        
        redis_client.setex(cache_key, 3600, json.dumps({'books': books_json}))


        return {'books': books_json}, 200
