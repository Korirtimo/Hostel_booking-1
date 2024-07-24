from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_mail import Mail, Message
import stripe
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hostel.db'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_password'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
admin = Admin(app, name='hostel', template_mode='bootstrap3')

stripe.api_key = 'your_stripe_secret_key'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class RoomType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_type_id = db.Column(db.Integer, db.ForeignKey('room_type.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash('Registered successfully')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    if request.method == 'POST':
        room_type_id = request.form['room_type']
        check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
        check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
        new_booking = Booking(user_id=current_user.id, room_type_id=room_type_id, check_in=check_in, check_out=check_out)
        db.session.add(new_booking)
        db.session.commit()
        flash('Booking successful')
        return redirect(url_for('index'))
    room_types = RoomType.query.all()
    return render_template('booking.html', room_types=room_types)

@app.route('/charge', methods=['POST'])
@login_required
def charge():
    amount = 500  # Amount in cents

    customer = stripe.Customer.create(
        email=current_user.email,
        source=request.form['stripeToken']
    )

    charge = stripe.Charge.create(
        customer=customer.id,
        amount=amount,
        currency='usd',
        description='Hostel Booking'
    )

    # Assuming the booking is already created, you might want to update its status here

    return render_template('charge.html', amount=amount)

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
        check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
        available_rooms = RoomType.query.filter(
            ~RoomType.id.in_(
                db.session.query(Booking.room_type_id).filter(
                    (Booking.check_in <= check_out) & (Booking.check_out >= check_in)
                )
            )
        ).all()
        return render_template('search_results.html', rooms=available_rooms)
    return render_template('search.html')

@app.route('/review', methods=['GET', 'POST'])
@login_required
def review():
    if request.method == 'POST':
        rating = request.form['rating']
        comment = request.form['comment']
        new_review = Review(user_id=current_user.id, rating=rating, comment=comment)
        db.session.add(new_review)
        db.session.commit()
        flash('Thank you for your review')
        return redirect(url_for('index'))
    return render_template('review.html')

@app.route('/gallery')
def gallery():
    photos = Photo.query.all()
    return render_template('gallery.html', photos=photos)

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    mail.send(msg)

class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

admin.add_view(AdminModelView(User, db.session))
admin.add_view(AdminModelView(RoomType, db.session))
admin.add_view(AdminModelView(Booking, db.session))
admin.add_view(AdminModelView(Review, db.session))
admin.add_view(AdminModelView(Photo, db.session))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)