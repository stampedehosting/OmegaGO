"""
Decorator Utilities
Authorization and permission decorators for the Agency Engine
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity
from app.models import User, Agent

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def agent_or_admin_required(f):
    """Decorator to require agent or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        claims = get_jwt()
        user_role = claims.get('role')
        if user_role not in ['agent', 'admin', 'manager']:
            return jsonify({'error': 'Agent or admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def manager_or_admin_required(f):
    """Decorator to require manager or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        claims = get_jwt()
        user_role = claims.get('role')
        if user_role not in ['manager', 'admin']:
            return jsonify({'error': 'Manager or admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def active_user_required(f):
    """Decorator to ensure user account is active"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'Account is inactive or not found'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def agent_profile_required(f):
    """Decorator to ensure user has an agent profile"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile required'}), 404
        
        return f(*args, **kwargs)
    return decorated_function

def own_resource_or_admin(resource_user_id_field='user_id'):
    """
    Decorator to ensure user can only access their own resources or is admin
    
    Args:
        resource_user_id_field: The field name in kwargs that contains the user_id of the resource
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            claims = get_jwt()
            
            # Admin can access any resource
            if claims.get('role') == 'admin':
                return f(*args, **kwargs)
            
            # Check if user is accessing their own resource
            resource_user_id = kwargs.get(resource_user_id_field)
            if resource_user_id and int(resource_user_id) != current_user_id:
                return jsonify({'error': 'Access denied - can only access own resources'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def own_agent_or_admin(agent_id_field='agent_id'):
    """
    Decorator to ensure user can only access their own agent data or is admin
    
    Args:
        agent_id_field: The field name in kwargs that contains the agent_id
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            claims = get_jwt()
            
            # Admin can access any agent
            if claims.get('role') == 'admin':
                return f(*args, **kwargs)
            
            # Check if user is accessing their own agent data
            agent_id = kwargs.get(agent_id_field)
            if agent_id:
                agent = Agent.query.get(agent_id)
                if not agent or agent.user_id != current_user_id:
                    return jsonify({'error': 'Access denied - can only access own agent data'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(max_requests=100, window_seconds=3600):
    """
    Simple rate limiting decorator (in production, use Redis or similar)
    
    Args:
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This is a placeholder implementation
            # In production, implement proper rate limiting with Redis
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_json_content_type(f):
    """Decorator to ensure request has JSON content type"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        return f(*args, **kwargs)
    return decorated_function

def log_api_access(f):
    """Decorator to log API access for auditing"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        import logging
        from flask import request
        
        logger = logging.getLogger(__name__)
        
        try:
            current_user_id = get_jwt_identity()
            claims = get_jwt()
            user_role = claims.get('role', 'unknown')
            
            logger.info(f"API Access - User: {current_user_id}, Role: {user_role}, "
                       f"Endpoint: {request.endpoint}, Method: {request.method}, "
                       f"IP: {request.remote_addr}")
        except Exception:
            # Don't fail the request if logging fails
            pass
        
        return f(*args, **kwargs)
    return decorated_function

def require_integration(integration_name):
    """
    Decorator to ensure required integration is configured
    
    Args:
        integration_name: Name of the required integration (e.g., 'medicarepro', 'agent_methods')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import current_app
            
            # Check if integration API key is configured
            config_key = f"{integration_name.upper()}_API_KEY"
            if not current_app.config.get(config_key):
                return jsonify({
                    'error': f'{integration_name} integration not configured'
                }), 503
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def handle_database_errors(f):
    """Decorator to handle common database errors"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from sqlalchemy.exc import IntegrityError, DataError
        from app import db
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            return f(*args, **kwargs)
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Database integrity error: {e}")
            
            if 'unique constraint' in str(e).lower():
                return jsonify({'error': 'Resource already exists'}), 409
            elif 'foreign key constraint' in str(e).lower():
                return jsonify({'error': 'Referenced resource not found'}), 400
            else:
                return jsonify({'error': 'Database constraint violation'}), 400
                
        except DataError as e:
            db.session.rollback()
            logger.error(f"Database data error: {e}")
            return jsonify({'error': 'Invalid data format'}), 400
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected database error: {e}")
            return jsonify({'error': 'Database operation failed'}), 500
    
    return decorated_function

def cache_response(timeout=300):
    """
    Decorator to cache API responses (placeholder implementation)
    
    Args:
        timeout: Cache timeout in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This is a placeholder implementation
            # In production, implement proper caching with Redis or similar
            return f(*args, **kwargs)
        return decorated_function
    return decorator
