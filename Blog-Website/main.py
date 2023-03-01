import os
import smtplib
from datetime import date
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import NoResultFound, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, CreateContactForm

MY_EMAIL = os.getenv("EMAIL")
MY_PASSWORD = os.getenv("PASSWORD")

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

Bootstrap(app)
db = SQLAlchemy(app)
ckeditor = CKEditor(app)
login_manager = LoginManager(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)

    posts = db.relationship("BlogPost", backref="users")
    comments = db.relationship("Comment", backref="users")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    comments = db.relationship("Comment", backref="blog_posts")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    text = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()


# Python Decorator function for admin verification
def admin_only(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            if current_user.id == 1:
                return function(*args, **kwargs)
            else:
                return abort(403)
        except AttributeError:
            return abort(403)

    return wrapper


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.execute(db.select(User).filter_by(id=user_id)).scalar_one()
    except NoResultFound:
        return None


@app.route('/')
def get_all_posts():
    posts = db.session.execute(db.select(BlogPost)).scalars()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data
        password = generate_password_hash(form.password.data)
        name = form.name.data

        try:
            new_user = User(email=email, password=password, name=name)  # type: ignore
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            flash("The Email you have entered has been taken, try to use a different Email!")
            return redirect(url_for("register"))
        else:
            login_user(new_user)
            return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        try:
            user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one()
        except NoResultFound:
            flash("Sorry, Wrong Email, Try to use a different Email!")
            return redirect(url_for("login"))
        else:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Sorry, Wrong Password, Try to use a different Password!")
                return redirect(url_for("login"))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()

    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(author_id=current_user.id, post_id=post_id, text=form.comment.data)
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("Please Login or Register to Submit your Comment!")
            return redirect(url_for("login"))

    requested_post = db.session.execute(db.select(BlogPost).filter_by(id=post_id)).scalar_one()

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = CreateContactForm()

    if form.validate_on_submit():
        data = form.data
        name = data["name"]
        email = data["email"]
        phone = data["phone"]
        message = data["message"]

        try:
            with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
                connection.starttls()
                connection.login(MY_EMAIL, MY_PASSWORD)
                connection.sendmail(from_addr=MY_EMAIL,
                                    to_addrs=MY_EMAIL,
                                    msg=f"subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\n"
                                        f"Message: {message}".encode("utf-8"))
        except smtplib.SMTPAuthenticationError:
            return render_template("contact.html", form=form, h1="Successfully Send Your Message")

    else:
        return render_template("contact.html", form=form, h1="Contact Me")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            author_id=current_user.id,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()

        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=form)


@app.route("/edit-post/<post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.session.execute(db.select(BlogPost).filter_by(id=post_id)).scalar_one()
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()

        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, goal="edit")


@app.route("/delete/<post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.session.execute(db.select(BlogPost).filter_by(id=post_id)).scalar_one()
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
