import os
import sys
from flask import Flask, render_template, request, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
import click
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import login_user
from flask_login import login_required, logout_user
from flask_login import login_required, current_user

# 检测操作系统，设置不同的 SQLite URI 前缀
WIN = sys.platform.startswith('win')
if WIN:
    prefix = 'sqlite:///'
else:
    prefix = 'sqlite:////'

# 创建 Flask 应用实例
app = Flask(__name__)
login_manager = LoginManager(app) # 实例化扩展类
@login_manager.user_loader
def load_user(user_id): # 创建用户加载回调函数，接受用户 ID 作为参数
    user = User.query.get(int(user_id)) # 用 ID 作为 User 模型的主键查询对应的用户
    return user # 返回用户对象

# 配置 SQLite 数据库路径
# app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(app.root_path, 'data.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_DATABASE_URI'] = prefix +os.path.join(os.path.dirname(app.root_path), os.getenv('DATABASE_FILE','data.db'))
# 关闭对模型修改的监控
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化 SQLAlchemy 扩展
db = SQLAlchemy(app)
#初始化login_manager扩展
login_manager.login_view = 'login'# 设置登录视图的端点


# 定义 User 模型，对应数据库中的 user 表
class User(db.Model,UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    username = db.Column(db.String(20))  # 用户名
    password_hash = db.Column(db.String(128))  # 密码散列值
    def set_password(self, password): # 用来设置密码的方法，接受密码作为参数
        self.password_hash = generate_password_hash(password)# 将生成的密码保持到对应字段

    def validate_password(self, password):
        return check_password_hash(self.password_hash, password) # 返回布尔值


# 定义 Movie 模型，对应数据库中的 movie 表
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(60))
    year = db.Column(db.String(4))


# 生成或更新管理员账户的命令行函数
@app.cli.command()
@click.option('--username', prompt=True, help='The username used to login.')
@click.option('--password', prompt=True, hide_input=True,
confirmation_prompt=True, help='The password used to login.')
def admin(username, password):
    """Create user."""
    db.create_all()
    user = User.query.first()
    if user is not None:
        click.echo('Updating user...')
        user.username = username
        user.set_password(password) # 设置密码
    else:
        click.echo('Creating user...')
        user = User(username=username, name='Admin')
        user.set_password(password) # 设置密码
        db.session.add(user)
    db.session.commit() # 提交数据库会话
    click.echo('Done.')

# 设置应用的 SECRET_KEY，用于表单和 session 安全
app.config['SECRET_KEY'] = 'dev'

#用户登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Invalid input.')
            return redirect(url_for('login'))
        user = User.query.first()
# 验证用户名和密码是否一致
        if username == user.username and user.validate_password(password):
            login_user(user)  # 登入用户
            flash('Login success.')
            return redirect(url_for('index'))  # 重定向到主页
        flash('Invalid username or password.')  # 如果验证失败，显示错误消息
        return redirect(url_for('login'))  # 重定向回登录页面
    return render_template('login.html')

#登出
@app.route('/logout')
@login_required # 用于视图保护，后面会详细介绍
def logout():
    logout_user() # 登出用户
    flash('Goodbye.')
    return redirect(url_for('index')) # 重定向回首页

# 定义主页视图函数，处理 GET 和 POST 请求
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not current_user.is_authenticated: # 如果当前用户未认证
            return redirect(url_for('index')) # 重定向到主页

        title = request.form.get('title')
        year = request.form.get('year')

        # 验证表单数据是否有效
        if not title or not year or len(year) > 4 or len(title) > 60:
            flash('Invalid input.')
            return redirect(url_for('index'))

        # 创建电影对象并保存到数据库
        movie = Movie(title=title, year=year)
        db.session.add(movie)
        db.session.commit()
        flash('Item created.')
        return redirect(url_for('index'))
    # 查询所有电影记录并渲染主页模板
    movies = Movie.query.all()
    return render_template('index.html', movies=movies)

# 处理 404 错误，显示自定义的 404 页面
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# 注入模板上下文的处理函数，向模板中注入当前第一个用户对象
@app.context_processor
def inject_user():
    user = User.query.first()
    return dict(user=user)

# 定义编辑电影信息的视图函数，处理 GET 和 POST 请求
@app.route('/movie/edit/<int:movie_id>', methods=['GET', 'POST'])
@login_required # 登录保护
def edit(movie_id):
    # 查询指定电影 ID 的记录，若不存在则返回 404 错误页面
    movie = Movie.query.get_or_404(movie_id)

    if request.method == 'POST':
        title = request.form['title']
        year = request.form['year']

        # 验证表单数据是否有效
        if not title or not year or len(year) != 4 or len(title) > 60:
            flash('Invalid input.')
            return redirect(url_for('edit', movie_id=movie_id))

        # 更新电影记录并提交到数据库
        movie.title = title
        movie.year = year
        db.session.commit()
        flash('Item updated.')
        return redirect(url_for('index'))

    # 渲染编辑页面模板，并传入当前电影对象
    return render_template('edit.html', movie=movie)

# 定义删除电影记录的视图函数，处理 POST 请求
@app.route('/movie/delete/<int:movie_id>', methods=['POST'])
@login_required # 登录保护
def delete(movie_id):
    # 查询指定电影 ID 的记录，若不存在则返回 404 错误页面
    movie = Movie.query.get_or_404(movie_id)
    # 删除电影记录并提交到数据库
    db.session.delete(movie)
    db.session.commit()
    flash('Item deleted.')
    return redirect(url_for('index'))

#支持设置用户名字
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form['name']
        if not name or len(name) > 20:
            flash('Invalid input.')
            return redirect(url_for('settings'))
        current_user.name = name
        # current_user 会返回当前登录用户的数据库记录对象
        # 等同于下面的用法
        # user = User.query.first()
        # user.name = name
        db.session.commit()
        flash('Settings updated.')
        return redirect(url_for('index'))
    return render_template('settings.html')


# 自定义命令，生成假数据
@app.cli.command()
def forge():
    """Generate fake data."""
    db.create_all()
    name = 'Grey Li'
    movies = [
        {'title': 'My Neighbor Totoro', 'year': '1988'},
        {'title': 'Dead Poets Society', 'year': '1989'},
        {'title': 'A Perfect World', 'year': '1993'},
        {'title': 'Leon', 'year': '1994'},
        {'title': 'Mahjong', 'year': '1996'},
        {'title': 'Swallowtail Butterfly', 'year': '1996'},
        {'title': 'King of Comedy', 'year': '1999'},
        {'title': 'Devils on the Doorstep', 'year': '1999'},
        {'title': 'WALL-E', 'year': '2008'},
        {'title': 'The Pork of Music', 'year': '2012'},
    ]

    user = User(name=name)
    db.session.add(user)
    for m in movies:
        movie = Movie(title=m['title'], year=m['year'])
        db.session.add(movie)
    db.session.commit()
    click.echo('Done.')

# 自定义命令，初始化数据库
@app.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    """Initialize the database."""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')


if __name__ == '__main__':
    app.run()
