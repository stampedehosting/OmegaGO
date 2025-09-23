"""
Validation Utilities
Common validation functions for the Agency Engine
"""

import re
from typing import Dict, Any

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email or not isinstance(email, str):
        return False
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email.strip()) is not None

def validate_password(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    if not password or not isinstance(password, str):
        return {'valid': False, 'message': 'Password is required'}
    
    if len(password) < 8:
        return {'valid': False, 'message': 'Password must be at least 8 characters long'}
    
    if len(password) > 128:
        return {'valid': False, 'message': 'Password must be less than 128 characters'}
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return {'valid': False, 'message': 'Password must contain at least one uppercase letter'}
    
    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return {'valid': False, 'message': 'Password must contain at least one lowercase letter'}
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return {'valid': False, 'message': 'Password must contain at least one number'}
    
    # Check for at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return {'valid': False, 'message': 'Password must contain at least one special character'}
    
    return {'valid': True, 'message': 'Password is valid'}

def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number (10 or 11 digits)
    return len(digits_only) in [10, 11] and (len(digits_only) == 10 or digits_only[0] == '1')

def validate_agent_id(agent_id: str) -> bool:
    """Validate agent ID format"""
    if not agent_id or not isinstance(agent_id, str):
        return False
    
    # Agent ID should be alphanumeric, 3-20 characters
    return re.match(r'^[A-Za-z0-9]{3,20}$', agent_id) is not None

def validate_license_number(license_number: str) -> bool:
    """Validate insurance license number format"""
    if not license_number or not isinstance(license_number, str):
        return False
    
    # License number should be alphanumeric, 5-50 characters
    return re.match(r'^[A-Za-z0-9\-]{5,50}$', license_number) is not None

def validate_state_code(state_code: str) -> bool:
    """Validate US state code"""
    if not state_code or not isinstance(state_code, str):
        return False
    
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC'  # District of Columbia
    }
    
    return state_code.upper() in valid_states

def validate_zip_code(zip_code: str) -> bool:
    """Validate US ZIP code format"""
    if not zip_code or not isinstance(zip_code, str):
        return False
    
    # Support both 5-digit and 9-digit ZIP codes
    return re.match(r'^\d{5}(-\d{4})?$', zip_code) is not None

def validate_currency_amount(amount: Any) -> bool:
    """Validate currency amount (positive number with up to 2 decimal places)"""
    try:
        float_amount = float(amount)
        return float_amount >= 0 and round(float_amount, 2) == float_amount
    except (ValueError, TypeError):
        return False

def validate_percentage(percentage: Any) -> bool:
    """Validate percentage (0-100)"""
    try:
        float_percentage = float(percentage)
        return 0 <= float_percentage <= 100
    except (ValueError, TypeError):
        return False

def validate_date_string(date_string: str, format_string: str = '%Y-%m-%d') -> bool:
    """Validate date string format"""
    if not date_string or not isinstance(date_string, str):
        return False
    
    try:
        from datetime import datetime
        datetime.strptime(date_string, format_string)
        return True
    except ValueError:
        return False

def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not url or not isinstance(url, str):
        return False
    
    url_pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
    return re.match(url_pattern, url) is not None

def sanitize_string(input_string: str, max_length: int = None) -> str:
    """Sanitize string input"""
    if not input_string or not isinstance(input_string, str):
        return ''
    
    # Remove leading/trailing whitespace
    sanitized = input_string.strip()
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    
    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_course_quiz_data(quiz_data: list) -> Dict[str, Any]:
    """Validate course quiz question data structure"""
    if not isinstance(quiz_data, list):
        return {'valid': False, 'message': 'Quiz data must be a list'}
    
    if len(quiz_data) == 0:
        return {'valid': True, 'message': 'Empty quiz is valid'}
    
    for i, question in enumerate(quiz_data):
        if not isinstance(question, dict):
            return {'valid': False, 'message': f'Question {i+1} must be an object'}
        
        required_fields = ['id', 'question', 'options', 'correct_answer']
        for field in required_fields:
            if field not in question:
                return {'valid': False, 'message': f'Question {i+1} missing required field: {field}'}
        
        if not isinstance(question['options'], list) or len(question['options']) < 2:
            return {'valid': False, 'message': f'Question {i+1} must have at least 2 options'}
        
        if question['correct_answer'] not in question['options']:
            return {'valid': False, 'message': f'Question {i+1} correct answer must be one of the options'}
    
    return {'valid': True, 'message': 'Quiz data is valid'}

def validate_social_media_config(config: dict) -> Dict[str, Any]:
    """Validate social media configuration data"""
    if not isinstance(config, dict):
        return {'valid': False, 'message': 'Configuration must be an object'}
    
    valid_platforms = ['facebook', 'instagram', 'linkedin', 'twitter']
    
    for platform, platform_config in config.items():
        if platform not in valid_platforms:
            return {'valid': False, 'message': f'Unsupported platform: {platform}'}
        
        if not isinstance(platform_config, dict):
            return {'valid': False, 'message': f'{platform} configuration must be an object'}
        
        # Each platform should have at least an access_token or api_key
        if not any(key in platform_config for key in ['access_token', 'api_key', 'token']):
            return {'valid': False, 'message': f'{platform} configuration missing authentication token'}
    
    return {'valid': True, 'message': 'Social media configuration is valid'}
