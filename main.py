from flask import Flask, render_template, request, flash, url_for, redirect, session
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from flask_mysqldb import MySQL
from functools import wraps

app = Flask(__name__)

# MySQL configs
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = '<USER>'
app.config['MYSQL_PASSWORD'] = '<PASSWORD>'
app.config['MYSQL_DB'] = '<DB NAME>'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mySql = MySQL(app)


@app.route('/')
# Home page (default)
def Home():
    return render_template('home.html')


@app.route('/about')
# About page
def About():
    return render_template('about.html')


@app.route('/articles')
# Article list
def Articles():
    # Get articles list from DB
    cursor = mySql.connection.cursor()
    result = cursor.execute('SELECT * FROM articles;')
    if result > 0:
        articles = cursor.fetchall()
        cursor.close()
        return render_template('articles.html', articles=articles)
    else:
        return render_template('articles.html', msg='No articles found')


@app.route('/article/<string:id>')
# Individual article page
def Article(id):
    cursor = mySql.connection.cursor()
    result = cursor.execute('SELECT * FROM articles WHERE id=%s', [id])
    if result > 0:
        article = cursor.fetchone()
        cursor.close()
        return render_template('article.html', article=article)
    else:
        return render_template('article.html', error='Invalid article ID')


class RegisterForm (Form):
    # Register form class
    name = StringField('Name', [validators.length(min=1, max=100)])
    username = StringField('Username', [validators.length(min=4, max=25)])
    email = StringField('Email', [validators.length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.data_required(),
        validators.length(min=6, max=50),
        validators.equal_to('confirm', message='Password does not match')
    ])
    confirm = PasswordField('Confirm')


@app.route('/register', methods=['POST', 'GET'])
# Register page
def Register():
    form = RegisterForm(request.form)
    if(request.method == 'POST' and form.validate()):
        # New user registration
        name = form.name.data
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))
        cursor = mySql.connection.cursor()
        result = cursor.execute(
            'SELECT * FROM users WHERE username=%s', [username])
        if(result > 0):
            # Username already taken
            flash('Userame already exists', 'danger')
            return render_template('register.html', form=form)
        else:
            # Register user details into DB
            cursor.execute('INSERT INTO users(name,email,username,password) VALUES(%s, %s, %s, %s)',
                           (name, email, username, password))
            mySql.connection.commit()
        cursor.close()

        flash('You are now registered and can login', 'success')
        return redirect(url_for('Home'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
# Login page
def Login():
    if(request.method == 'POST'):
        username = request.form['username']
        entered_password = request.form['password']

        cursor = mySql.connection.cursor()
        result = cursor.execute(
            'SELECT * FROM users WHERE username=%s', [username])
        if(result > 0):
            data = cursor.fetchone()
            if(sha256_crypt.verify(entered_password, data['password'])):
                # Password matched
                session['logged_in'] = True
                session['username'] = username
                flash('You are now logged in', 'success')
                return redirect(url_for('Dashboard'))
            else:
                # Password doesn't match
                return render_template('login.html', error='Invalid password')
        else:
            # User doesn't exist
            return render_template('login.html', error='Invalid user')
        cursor.close()

    return render_template('login.html')


@app.route('/logout')
# Logout link
def Logout():
    session.clear()
    flash('You have successfully logged out', 'success')
    return redirect(url_for('Login'))


# Wrapper function for authenticated pages
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('You have to be logged in to view this page', 'danger')
            return redirect(url_for('Login'))
    return wrap


class AddArticleForm(Form):
    # Add article form class
    title = StringField('Title', [validators.length(min=4, max=100)])
    body = TextAreaField('Body', [validators.length(min=30)])


@app.route('/add_article', methods=['GET', 'POST'])
@is_logged_in
# Add article page [Authenticated]
def AddArticle():
    form = AddArticleForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        body = form.body.data

        # Insert into DB
        cursor = mySql.connection.cursor()
        cursor.execute(
            'INSERT INTO articles(author,title,body) VALUES (%s,%s,%s)', (session['username'], title, body))
        mySql.connection.commit()
        cursor.close()
        # Redirect back to dashboard
        flash("Article has been added successfully", 'success')
        return redirect(url_for('Dashboard'))
    return render_template('add_article.html', form=form)


@app.route('/edit_article/<string:id>', methods=['GET', 'POST'])
@is_logged_in
# Page to edit an article [Authenticated]
def EditArticle(id):
    form = AddArticleForm(request.form)

    # Get current values from DB
    cursor = mySql.connection.cursor()
    result = cursor.execute('SELECT * FROM articles WHERE id=%s', [id])
    if result > 0:
        data = cursor.fetchone()
        form.title.data = data['title']
        form.body.data = data['body']

    if request.method == 'POST' and form.validate():
        title = request.form['title']
        body = request.form['body']

        # Update new values
        cursor.execute('UPDATE articles SET title=%s, body=%s WHERE id=%s', [
                       title, body, id])
        mySql.connection.commit()

        # Redirect to dashboard
        flash('Article updated', 'success')
        cursor.close()
        return redirect(url_for('Dashboard'))
    cursor.close()
    return render_template('edit_article.html', form=form)


@app.route('/delete_article/<string:id>')
@is_logged_in
# Delete an article [Authenticated]
def DeleteArticle(id):
    # Delete article from db
    cursor = mySql.connection.cursor()
    cursor.execute('DELETE FROM articles WHERE id=%s', [id])
    mySql.connection.commit()
    cursor.close()

    # Redirect to dashboard
    flash('Artical deleted successfully', 'success')
    return redirect(url_for('Dashboard'))


@app.route('/dashboard')
@is_logged_in
# User Dashboard [Authenticated]
def Dashboard():
    # Get the user's articles list from DB
    cursor = mySql.connection.cursor()
    result = cursor.execute(
        'SELECT * FROM articles WHERE author=%s;', [session['username']])
    if result > 0:
        articles = cursor.fetchall()
        cursor.close()
        return render_template('dashboard.html', articles=articles)
    else:
        return render_template('dashboard.html', msg='Click the button to add your first article')


if __name__ == '__main__':
    app.secret_key = "yoursecretkeyhere"
    app.run(debug=True)
