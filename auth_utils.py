"""
Authentication utilities for JWT token handling and password verification.
"""
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify


def get_jwt_secret():
    """Get JWT secret key from environment."""
    secret = os.environ.get('JWT_SECRET_KEY')
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY not set in environment")
    return secret


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def create_jwt_token(user_email: str, role: str, user_id: int, expires_days: int = 7) -> str:
    """Create a JWT token with user info."""
    payload = {
        'user_email': user_email,
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + timedelta(days=expires_days),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, get_jwt_secret(), algorithm='HS256')
    return token


def decode_jwt_token(token: str) -> dict:
    """Decode and verify a JWT token. Returns payload or raises exception."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")


def require_auth(f):
    """Decorator to require valid JWT token. Adds 'current_user' to kwargs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.replace('Bearer ', '', 1)
        try:
            payload = decode_jwt_token(token)
            kwargs['current_user'] = payload
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({'error': str(e)}), 401
    
    return decorated


def require_role(allowed_roles: list):
    """Decorator to require specific role(s). Use after @require_auth."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                return jsonify({'error': 'Authentication required'}), 401
            
            user_role = current_user.get('role', 'user')
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator
