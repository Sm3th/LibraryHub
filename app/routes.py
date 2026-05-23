from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .models import Favorite, db, User, Book, Borrow, ReadingGoal
from datetime import datetime, timedelta
from sqlalchemy import distinct
from collections import defaultdict
import random

main = Blueprint('main', __name__)


def _require_login():
    flash('Please log in to continue.', 'warning')
    return redirect(url_for('main.login'))


def _get_favorite_ids(user_id):
    rows = db.session.query(Favorite.book_id).filter_by(user_id=user_id).all()
    return {r.book_id for r in rows}


# Home / Library
@main.route('/')
def home():
    if 'user_id' not in session:
        flash('Please log in to view your library.', 'warning')
        return redirect(url_for('main.login'))

    user_id         = session['user_id']
    search_query    = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '')
    status_filter   = request.args.get('status', '')
    favorites_only  = bool(request.args.get('favorites'))
    sort_by         = request.args.get('sort', 'date_added')

    query = Book.query.filter_by(user_id=user_id)

    if search_query:
        query = query.filter(
            (Book.title.ilike(f'%{search_query}%')) |
            (Book.author.ilike(f'%{search_query}%'))
        )
    if category_filter:
        query = query.filter_by(category=category_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if favorites_only:
        query = query.join(Favorite).filter(Favorite.user_id == user_id)

    # Sorting — Book.x.is_(None) pushes NULLs to end in ASC order (0 < 1)
    if sort_by == 'title_asc':
        query = query.order_by(Book.title.asc())
    elif sort_by == 'title_desc':
        query = query.order_by(Book.title.desc())
    elif sort_by == 'author':
        query = query.order_by(Book.author.asc())
    elif sort_by == 'year_desc':
        query = query.order_by(Book.published_year.is_(None), Book.published_year.desc())
    elif sort_by == 'year_asc':
        query = query.order_by(Book.published_year.is_(None), Book.published_year.asc())
    elif sort_by == 'rating':
        query = query.order_by(Book.rating.is_(None), Book.rating.desc())
    else:  # date_added (default)
        query = query.order_by(Book.date_added.is_(None), Book.date_added.desc())

    books = query.all()

    all_books       = Book.query.filter_by(user_id=user_id).all()
    all_books_count = len(all_books)
    read_count      = sum(1 for b in all_books if b.status == 'Read')
    reading_count   = sum(1 for b in all_books if b.status == 'Reading')

    favorite_book_ids = _get_favorite_ids(user_id)

    cat_rows   = db.session.query(distinct(Book.category)).filter(
        Book.user_id == user_id, Book.category.isnot(None), Book.category != ''
    ).all()
    categories = sorted([r[0] for r in cat_rows])

    featured_book = random.choice(books) if books else None

    return render_template(
        'index.html',
        books=books,
        featured_book=featured_book,
        favorite_book_ids=favorite_book_ids,
        search_query=search_query,
        category_filter=category_filter,
        status_filter=status_filter,
        favorites_only=favorites_only,
        categories=categories,
        all_books_count=all_books_count,
        read_count=read_count,
        reading_count=reading_count,
        sort_by=sort_by,
    )


# Add Book
@main.route('/add-book', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return _require_login()

    if request.method == 'POST':
        title          = request.form.get('title', '').strip()
        author         = request.form.get('author', '').strip()
        published_year = request.form.get('published_year', '').strip()
        isbn           = request.form.get('isbn', '').strip() or None
        category       = request.form.get('category', '').strip() or None
        status         = request.form.get('status', 'Unread')
        fmt            = request.form.get('format', 'Physical')
        description    = request.form.get('description', '').strip() or None

        if not title or not author:
            flash('Title and author are required.', 'danger')
            return render_template('add_book.html')

        try:
            year = int(published_year) if published_year else None
        except ValueError:
            flash('Published year must be a number.', 'danger')
            return render_template('add_book.html')

        try:
            new_book = Book(
                title=title, author=author, published_year=year,
                isbn=isbn, category=category, status=status,
                format=fmt, description=description, user_id=session['user_id']
            )
            db.session.add(new_book)
            db.session.commit()
            flash(f'"{title}" added to your library!', 'success')
            return redirect(url_for('main.home'))
        except Exception as e:
            db.session.rollback()
            err = str(e)
            if 'UniqueViolation' in err or 'unique constraint' in err.lower() or 'UNIQUE constraint' in err:
                flash('A book with this ISBN already exists in the system.', 'danger')
            else:
                flash(f'Error adding book: {e}', 'danger')

    return render_template('add_book.html')


# Edit Book
@main.route('/edit-book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        flash('You are not authorized to edit this book.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        title          = request.form.get('title', '').strip()
        author         = request.form.get('author', '').strip()
        published_year = request.form.get('published_year', '').strip()
        isbn           = request.form.get('isbn', '').strip() or None
        category       = request.form.get('category', '').strip() or None
        status         = request.form.get('status', 'Unread')
        fmt            = request.form.get('format', 'Physical')
        description    = request.form.get('description', '').strip() or None

        if not title or not author:
            flash('Title and author are required.', 'danger')
            return render_template('edit_book.html', book=book)

        try:
            year = int(published_year) if published_year else None
        except ValueError:
            flash('Published year must be a number.', 'danger')
            return render_template('edit_book.html', book=book)

        try:
            book.title = title; book.author = author; book.published_year = year
            book.isbn = isbn; book.category = category; book.status = status
            book.format = fmt; book.description = description
            db.session.commit()
            flash(f'"{title}" updated successfully!', 'success')
            return redirect(url_for('main.home'))
        except Exception as e:
            db.session.rollback()
            err = str(e)
            if 'UniqueViolation' in err or 'unique constraint' in err.lower() or 'UNIQUE constraint' in err:
                flash('A book with this ISBN already exists in the system.', 'danger')
            else:
                flash(f'Error updating book: {e}', 'danger')

    return render_template('edit_book.html', book=book)


# Delete Book
@main.route('/delete-book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        flash('You are not authorized to delete this book.', 'danger')
        return redirect(url_for('main.home'))

    try:
        db.session.delete(book)
        db.session.commit()
        flash(f'"{book.title}" deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting book: {e}', 'danger')

    return redirect(url_for('main.home'))


# Register
@main.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        name     = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not name or not email or not password:
            flash('All fields are required.', 'warning')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html')

        try:
            hashed   = User.hash_password(password)
            new_user = User(name=name, email=email, password_hash=hashed)
            db.session.add(new_user)
            db.session.commit()
            session['user']    = name
            session['user_id'] = new_user.id
            flash(f'Welcome to LibraryHub, {name}!', 'success')
            return redirect(url_for('main.home'))
        except Exception as e:
            db.session.rollback()
            flash(f'Registration error: {e}', 'danger')

    return render_template('register.html')


# Login
@main.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        session['user']    = user.name
        session['user_id'] = user.id
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('main.home'))

    return render_template('login.html')


# Logout
@main.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


# Toggle Favorite
@main.route('/toggle_favorite/<int:book_id>', methods=['POST'])
def toggle_favorite(book_id):
    if 'user_id' not in session:
        return _require_login()

    user_id  = session['user_id']
    favorite = Favorite.query.filter_by(user_id=user_id, book_id=book_id).first()

    if favorite:
        db.session.delete(favorite)
    else:
        db.session.add(Favorite(user_id=user_id, book_id=book_id))
    db.session.commit()

    return redirect(request.referrer or url_for('main.home'))


# Remove Favorite
@main.route('/remove-favorite/<int:book_id>', methods=['POST'])
def remove_favorite(book_id):
    if 'user_id' not in session:
        return _require_login()

    user_id  = session['user_id']
    favorite = Favorite.query.filter_by(user_id=user_id, book_id=book_id).first()

    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        flash('Removed from favorites.', 'success')

    return redirect(request.referrer or url_for('main.favorites'))


# Favorites Page
@main.route('/favorites')
def favorites():
    if 'user_id' not in session:
        return _require_login()

    user_id = session['user_id']
    favorite_books = (
        db.session.query(Book)
        .join(Favorite)
        .filter(Favorite.user_id == user_id)
        .all()
    )
    return render_template('favorites.html', favorite_books=favorite_books)


# Book Detail
@main.route('/book/<int:book_id>', methods=['GET', 'POST'])
def book_detail(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        if book.user_id != session['user_id']:
            flash('Not authorized.', 'danger')
            return redirect(url_for('main.home'))
        try:
            book.notes = request.form.get('note', '').strip() or None
            db.session.commit()
            flash('Note saved!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving note: {e}', 'danger')

    is_favorite = Favorite.query.filter_by(
        user_id=session['user_id'], book_id=book_id
    ).first() is not None

    return render_template('book_detail.html', book=book, is_favorite=is_favorite)


# Toggle Status — cycles Unread → Reading → Read → Unread
@main.route('/toggle_status/<int:book_id>', methods=['POST'])
def toggle_status(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.home'))

    cycle = {'Unread': 'Reading', 'Reading': 'Read', 'Read': 'Unread'}
    book.status = cycle.get(book.status, 'Reading')
    db.session.commit()
    flash(f'Status updated to "{book.status}".', 'success')
    return redirect(request.referrer or url_for('main.home'))


# Edit Notes
@main.route('/edit-notes/<int:book_id>', methods=['POST'])
def edit_notes(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.home'))

    try:
        book.notes = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Notes updated!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating notes: {e}', 'danger')

    return redirect(url_for('main.book_detail', book_id=book_id))


# Rate Book
@main.route('/rate/<int:book_id>', methods=['POST'])
def rate_book(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.home'))

    rating = request.form.get('rating', type=int)
    if rating and 1 <= rating <= 5:
        book.rating = rating
        db.session.commit()
        flash(f'Rated {rating}/5 stars!', 'success')
    else:
        book.rating = None
        db.session.commit()
        flash('Rating cleared.', 'info')

    return redirect(url_for('main.book_detail', book_id=book_id))


# Update Reading Progress
@main.route('/update-progress/<int:book_id>', methods=['POST'])
def update_progress(book_id):
    if 'user_id' not in session:
        return _require_login()

    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.home'))

    try:
        current_page = int(request.form.get('current_page', 0) or 0)
        total_pages  = request.form.get('total_pages', '').strip()
        book.current_page = max(0, current_page)
        book.total_pages  = int(total_pages) if total_pages else None
        if book.total_pages and book.current_page >= book.total_pages:
            book.status = 'Read'
            flash('Progress updated — marked as Read!', 'success')
        else:
            flash('Progress updated!', 'success')
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Error updating progress.', 'danger')

    return redirect(url_for('main.book_detail', book_id=book_id))


# Set Reading Goal
@main.route('/set-goal', methods=['POST'])
def set_goal():
    if 'user_id' not in session:
        return _require_login()

    user_id = session['user_id']
    year    = datetime.now().year

    try:
        goal_count = max(1, int(request.form.get('goal_count', 12)))
        goal = ReadingGoal.query.filter_by(user_id=user_id, year=year).first()
        if goal:
            goal.goal_count = goal_count
        else:
            db.session.add(ReadingGoal(user_id=user_id, year=year, goal_count=goal_count))
        db.session.commit()
        flash(f'Reading goal set to {goal_count} books for {year}!', 'success')
    except Exception:
        db.session.rollback()
        flash('Error setting goal.', 'danger')

    return redirect(request.referrer or url_for('main.stats'))


# Statistics
@main.route('/stats')
def stats():
    if 'user_id' not in session:
        return _require_login()

    user_id      = session['user_id']
    current_year = datetime.now().year

    all_books       = Book.query.filter_by(user_id=user_id).all()
    all_books_count = len(all_books)
    read_count      = sum(1 for b in all_books if b.status == 'Read')
    reading_count   = sum(1 for b in all_books if b.status == 'Reading')
    unread_count    = sum(1 for b in all_books if b.status == 'Unread')
    books_this_year = sum(1 for b in all_books if b.date_added and b.date_added.year == current_year)

    rated_books = [b for b in all_books if b.rating]
    avg_rating  = round(sum(b.rating for b in rated_books) / len(rated_books), 1) if rated_books else 0
    rating_dist = {i: sum(1 for b in rated_books if b.rating == i) for i in range(5, 0, -1)}
    max_rated   = max(rating_dist.values()) if any(rating_dist.values()) else 1

    cat_dict  = defaultdict(int)
    for b in all_books:
        cat_dict[b.category or 'Uncategorized'] += 1
    cat_counts = sorted(cat_dict.items(), key=lambda x: x[1], reverse=True)
    max_cat    = max(v for _, v in cat_counts) if cat_counts else 1

    goal        = ReadingGoal.query.filter_by(user_id=user_id, year=current_year).first()
    goal_count  = goal.goal_count if goal else 12
    goal_pct    = min(100, round(read_count / goal_count * 100)) if goal_count > 0 else 0
    goal_offset = round(326.73 * (1 - goal_pct / 100), 2)

    physical_count = sum(1 for b in all_books if b.format == 'Physical')
    ebook_count    = sum(1 for b in all_books if b.format == 'E-book')

    monthly_data = []
    for i in range(5, -1, -1):
        d     = datetime.now() - timedelta(days=30 * i)
        key   = d.strftime('%Y-%m')
        label = d.strftime('%b')
        count = sum(1 for b in all_books if b.date_added and b.date_added.strftime('%Y-%m') == key)
        monthly_data.append({'label': label, 'count': count})
    max_monthly = max(m['count'] for m in monthly_data) if monthly_data else 1

    top_books = sorted(rated_books, key=lambda b: b.rating, reverse=True)[:5]

    return render_template('stats.html',
        all_books_count=all_books_count,
        read_count=read_count,
        reading_count=reading_count,
        unread_count=unread_count,
        books_this_year=books_this_year,
        avg_rating=avg_rating,
        rating_dist=rating_dist,
        max_rated=max_rated,
        cat_counts=cat_counts,
        max_cat=max_cat,
        goal_count=goal_count,
        goal_pct=goal_pct,
        goal_offset=goal_offset,
        current_year=current_year,
        physical_count=physical_count,
        ebook_count=ebook_count,
        monthly_data=monthly_data,
        max_monthly=max_monthly,
        top_books=top_books,
    )


# Profile
@main.route('/profile')
def profile():
    if 'user_id' not in session:
        return _require_login()

    user_id  = session['user_id']
    user     = User.query.get_or_404(user_id)
    all_books = Book.query.filter_by(user_id=user_id).all()
    current_year = datetime.now().year

    read_count    = sum(1 for b in all_books if b.status == 'Read')
    reading_count = sum(1 for b in all_books if b.status == 'Reading')
    unread_count  = sum(1 for b in all_books if b.status == 'Unread')

    goal       = ReadingGoal.query.filter_by(user_id=user_id, year=current_year).first()
    goal_count = goal.goal_count if goal else 12
    goal_pct   = min(100, round(read_count / goal_count * 100)) if goal_count > 0 else 0

    cat_dict = defaultdict(int)
    for b in all_books:
        cat_dict[b.category or 'Uncategorized'] += 1
    favorite_genre = max(cat_dict.items(), key=lambda x: x[1])[0] if cat_dict else '—'

    rated_books = [b for b in all_books if b.rating]
    avg_rating  = round(sum(b.rating for b in rated_books) / len(rated_books), 1) if rated_books else 0

    initials = ''.join(w[0].upper() for w in user.name.split()[:2])

    return render_template('profile.html',
        user=user,
        initials=initials,
        all_books_count=len(all_books),
        read_count=read_count,
        reading_count=reading_count,
        unread_count=unread_count,
        goal_count=goal_count,
        goal_pct=goal_pct,
        current_year=current_year,
        favorite_genre=favorite_genre,
        avg_rating=avg_rating,
    )
