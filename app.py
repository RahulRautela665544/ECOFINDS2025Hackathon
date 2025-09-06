from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecofinds.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(80), nullable=False, default="New User")

    products = db.relationship('Product', backref='owner', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=False, default="/static/img/placeholder.png")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    qty = db.Column(db.Integer, default=1)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

CATEGORIES = ["Electronics", "Books", "Clothing", "Furniture", "Sports", "Other"]

# ---------- Helpers ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper

def current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

# ---------- Auth ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        username = request.form.get('username', 'New User').strip() or "New User"

        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for('register'))

        user = User(email=email, password_hash=generate_password_hash(password), username=username)
        db.session.add(user)
        db.session.commit()
        flash("Registered! Please log in.")
        return redirect(url_for('login'))
    return render_template('auth_register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash("Welcome back!")
            nxt = request.args.get('next')
            return redirect(nxt or url_for('browse'))
        flash("Invalid credentials.")
    return render_template('auth_login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Logged out.")
    return redirect(url_for('browse'))

# ---------- Profile (User Dashboard) ----------
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    user = current_user()
    if request.method == 'POST':
        user.username = request.form['username'].strip() or user.username
        # Allow email edit if you want:
        if request.form.get('email'):
            new_email = request.form['email'].strip().lower()
            if new_email != user.email and User.query.filter_by(email=new_email).first():
                flash("Email already in use.")
                return redirect(url_for('dashboard'))
            user.email = new_email
        db.session.commit()
        flash("Profile updated.")
        return redirect(url_for('dashboard'))
    return render_template('dashboard.html', user=user)

# ---------- Listings (CRUD) ----------
@app.route('/listings/new', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        category = request.form['category']
        price = float(request.form['price'])
        image_url = request.form.get('image_url', '/static/img/placeholder.png').strip() or '/static/img/placeholder.png'

        prod = Product(user_id=session['user_id'], title=title, description=description,
                       category=category, price=price, image_url=image_url)
        db.session.add(prod)
        db.session.commit()
        flash("Listing created.")
        return redirect(url_for('my_listings'))
    return render_template('add_product.html', categories=CATEGORIES)

@app.route('/listings/mine')
@login_required
def my_listings():
    items = Product.query.filter_by(user_id=session['user_id']).order_by(Product.created_at.desc()).all()
    return render_template('my_listings.html', items=items)

@app.route('/listings/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(pid):
    prod = Product.query.get_or_404(pid)
    if prod.user_id != session['user_id']:
        flash("Not authorized.")
        return redirect(url_for('my_listings'))
    if request.method == 'POST':
        prod.title = request.form['title'].strip()
        prod.description = request.form['description'].strip()
        prod.category = request.form['category']
        prod.price = float(request.form['price'])
        prod.image_url = request.form.get('image_url', '/static/img/placeholder.png').strip() or '/static/img/placeholder.png'
        db.session.commit()
        flash("Listing updated.")
        return redirect(url_for('my_listings'))
    return render_template('add_product.html', categories=CATEGORIES, prod=prod, editing=True)

@app.route('/listings/<int:pid>/delete', methods=['POST'])
@login_required
def delete_product(pid):
    prod = Product.query.get_or_404(pid)
    if prod.user_id != session['user_id']:
        flash("Not authorized.")
        return redirect(url_for('my_listings'))
    # remove from carts first
    CartItem.query.filter_by(product_id=pid).delete()
    db.session.delete(prod)
    db.session.commit()
    flash("Listing deleted.")
    return redirect(url_for('my_listings'))

# ---------- Browsing, Search, Filters, Detail ----------
@app.route('/')
def browse():
    q = request.args.get('q', '').strip().lower()
    category = request.args.get('category', '')
    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if q:
        query = query.filter(Product.title.ilike(f"%{q}%"))
    items = query.order_by(Product.created_at.desc()).all()
    return render_template('browse.html', items=items, categories=CATEGORIES, sel_category=category, q=q)

@app.route('/listings/<int:pid>')
def product_detail(pid):
    prod = Product.query.get_or_404(pid)
    return render_template('product_detail.html', p=prod)

# ---------- Cart & Purchases ----------
@app.route('/cart')
@login_required
def cart():
    uid = session['user_id']
    rows = db.session.query(CartItem, Product).join(Product, CartItem.product_id == Product.id).filter(CartItem.user_id == uid).all()
    total = sum(ci.qty * p.price for ci, p in rows)
    return render_template('cart.html', rows=rows, total=total)

@app.route('/cart/add/<int:pid>', methods=['POST'])
@login_required
def cart_add(pid):
    uid = session['user_id']
    item = CartItem.query.filter_by(user_id=uid, product_id=pid).first()
    if item:
        item.qty += 1
    else:
        item = CartItem(user_id=uid, product_id=pid, qty=1)
        db.session.add(item)
    db.session.commit()
    flash("Added to cart.")
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:cid>', methods=['POST'])
@login_required
def cart_remove(cid):
    item = CartItem.query.get_or_404(cid)
    if item.user_id != session['user_id']:
        flash("Not authorized.")
    else:
        db.session.delete(item)
        db.session.commit()
        flash("Removed from cart.")
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    uid = session['user_id']
    rows = CartItem.query.filter_by(user_id=uid).all()
    if not rows:
        flash("Cart is empty.")
        return redirect(url_for('cart'))
    for item in rows:
        p = Product.query.get(item.product_id)
        db.session.add(Purchase(user_id=uid, product_id=p.id, price_at_purchase=p.price))
        db.session.delete(item)
    db.session.commit()
    flash("Purchase complete!")
    return redirect(url_for('purchases'))

@app.route('/purchases')
@login_required
def purchases():
    uid = session['user_id']
    rows = db.session.query(Purchase, Product).join(Product, Purchase.product_id == Product.id).filter(Purchase.user_id == uid).order_by(Purchase.purchased_at.desc()).all()
    return render_template('purchases.html', rows=rows)

# ---------- Bootstrap DB ----------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
