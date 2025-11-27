"""Flask test fixture for Phase 3.1 extractor validation.

This file contains comprehensive Flask patterns to test all 9 Flask extractors:
- Application factories
- Extension registrations
- Request/response hooks
- Error handlers
- WebSocket handlers
- CLI commands
- CORS configurations
- Rate limiting
- Caching decorators
"""

import click
from flask import Flask, jsonify, render_template, request
from flask_caching import Cache
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy


# Flask Application Factory Pattern
def create_app(config_name='development'):
    """Create and configure Flask application."""
    app = Flask(__name__)

    # Configuration
    app.config.from_object(f'config.{config_name}')
    app.config.from_envvar('FLASK_CONFIG_FILE')

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)

    # Register blueprints
    from api.routes import api_bp
    from auth.routes import auth_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    return app


# Extension Registrations
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
cors = CORS(resources={r"/api/*": {"origins": "*"}})
limiter = Limiter(key_func=get_remote_address)
cache = Cache(config={'CACHE_TYPE': 'simple'})
socketio = SocketIO()


app = create_app('production')


# Request/Response Hooks
@app.before_request
def check_auth():
    """Verify authentication before each request."""
    if not request.headers.get('Authorization'):
        return jsonify({'error': 'Unauthorized'}), 401


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.before_first_request
def initialize_app():
    """Run initialization tasks on first request."""
    db.create_all()


@app.teardown_request
def cleanup_request(exception=None):
    """Clean up resources after request."""
    db.session.remove()


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Remove database session."""
    db.session.remove()


# Error Handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(ValueError)
def value_error(error):
    """Handle ValueError exceptions."""
    return jsonify({'error': str(error)}), 400


# WebSocket Handlers (Flask-SocketIO)
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    emit('status', {'msg': 'Connected'})


@socketio.on('message')
def handle_message(data):
    """Handle incoming WebSocket messages."""
    emit('response', {'data': data}, broadcast=True)


@socketio.on('join', namespace='/chat')
def handle_join(data):
    """Handle joining a chat room."""
    room = data['room']
    emit('announcement', {'msg': f'User joined {room}'}, room=room)


@socketio.on('disconnect', namespace='/notifications')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    emit('status', {'msg': 'Disconnected'})


# Flask CLI Commands
@app.cli.command('init-db')
@click.option('--drop', is_flag=True, help='Drop existing tables')
def init_db_command(drop):
    """Initialize the database."""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Database initialized.')


@app.cli.command()
def seed_data():
    """Seed initial data."""
    click.echo('Seeding database...')


# CORS Configurations
@cross_origin(origins='https://example.com')
def api_endpoint():
    """API endpoint with CORS."""
    return jsonify({'data': 'value'})


@cross_origin(origins='*')
def public_api():
    """Publicly accessible API."""
    return jsonify({'public': True})


# Rate Limiting
@app.route('/limited')
@limiter.limit("100 per hour")
def limited_endpoint():
    """Rate limited endpoint."""
    return jsonify({'message': 'Limited'})


@app.route('/strict')
@limiter.limit("10 per minute")
def strict_limited():
    """Strictly rate limited endpoint."""
    return jsonify({'message': 'Very limited'})


@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login endpoint with rate limit."""
    return jsonify({'token': 'abc123'})


# Caching Decorators
@app.route('/cached')
@cache.cached(timeout=300)
def cached_view():
    """View with caching."""
    return render_template('cached.html')


@app.route('/memoized/<int:user_id>')
@cache.memoize(timeout=600)
def user_profile(user_id):
    """Memoized user profile."""
    return jsonify({'user_id': user_id})


@app.route('/stats')
@cache.cached(timeout=60)
def statistics():
    """Cached statistics."""
    return jsonify({'stats': 'data'})


if __name__ == '__main__':
    socketio.run(app, debug=True)
