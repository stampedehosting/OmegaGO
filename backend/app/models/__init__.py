"""
Agency Engine Database Models
SQLAlchemy models for all database entities
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(db.Model):
    """User model for authentication and authorization"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='agent')  # admin, manager, agent
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agent_profile = db.relationship('Agent', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Agent(db.Model):
    """Agent profile model with performance tracking"""
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agent_id = db.Column(db.String(20), unique=True, nullable=False)  # External agent ID
    phone = db.Column(db.String(20))
    license_number = db.Column(db.String(50))
    license_state = db.Column(db.String(2))
    hire_date = db.Column(db.Date)
    territory = db.Column(db.String(100))
    commission_rate = db.Column(db.Float, default=0.0)
    
    # Performance metrics
    monthly_goal = db.Column(db.Float, default=0.0)
    ytd_sales = db.Column(db.Float, default=0.0)
    ytd_commissions = db.Column(db.Float, default=0.0)
    
    # Website and marketing
    website_url = db.Column(db.String(255))
    website_template = db.Column(db.String(50), default='default')
    social_media_connected = db.Column(db.Boolean, default=False)
    
    # CRM Integration
    medicarepro_id = db.Column(db.String(50))
    agent_methods_id = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    course_enrollments = db.relationship('CourseEnrollment', backref='agent', cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='agent', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'agent_id': self.agent_id,
            'phone': self.phone,
            'license_number': self.license_number,
            'license_state': self.license_state,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'territory': self.territory,
            'commission_rate': self.commission_rate,
            'monthly_goal': self.monthly_goal,
            'ytd_sales': self.ytd_sales,
            'ytd_commissions': self.ytd_commissions,
            'website_url': self.website_url,
            'website_template': self.website_template,
            'social_media_connected': self.social_media_connected,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Course(db.Model):
    """Training course model"""
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # onboarding, compliance, sales, etc.
    difficulty_level = db.Column(db.String(20), default='beginner')  # beginner, intermediate, advanced
    duration_minutes = db.Column(db.Integer)
    is_required = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Content
    video_url = db.Column(db.String(500))
    materials_url = db.Column(db.String(500))
    quiz_questions = db.Column(db.JSON)  # Store quiz data as JSON
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('CourseEnrollment', backref='course', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'difficulty_level': self.difficulty_level,
            'duration_minutes': self.duration_minutes,
            'is_required': self.is_required,
            'is_active': self.is_active,
            'video_url': self.video_url,
            'materials_url': self.materials_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class CourseEnrollment(db.Model):
    """Course enrollment and progress tracking"""
    __tablename__ = 'course_enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Progress tracking
    progress_percentage = db.Column(db.Float, default=0.0)
    time_spent_minutes = db.Column(db.Integer, default=0)
    quiz_score = db.Column(db.Float)
    quiz_attempts = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.String(20), default='enrolled')  # enrolled, in_progress, completed, failed
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'course_id': self.course_id,
            'enrolled_at': self.enrolled_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress_percentage': self.progress_percentage,
            'time_spent_minutes': self.time_spent_minutes,
            'quiz_score': self.quiz_score,
            'quiz_attempts': self.quiz_attempts,
            'status': self.status
        }

class Sale(db.Model):
    """Sales tracking model"""
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    
    # Sale details
    policy_number = db.Column(db.String(50))
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    
    # Financial details
    premium_amount = db.Column(db.Float, nullable=False)
    commission_amount = db.Column(db.Float, nullable=False)
    commission_rate = db.Column(db.Float)
    
    # Dates
    sale_date = db.Column(db.Date, nullable=False)
    effective_date = db.Column(db.Date)
    
    # Integration IDs
    medicarepro_lead_id = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'policy_number': self.policy_number,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'premium_amount': self.premium_amount,
            'commission_amount': self.commission_amount,
            'commission_rate': self.commission_rate,
            'sale_date': self.sale_date.isoformat(),
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Integration(db.Model):
    """API integration settings and credentials"""
    __tablename__ = 'integrations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # medicarepro, agent_methods, etc.
    is_active = db.Column(db.Boolean, default=True)
    
    # Encrypted credentials
    api_key = db.Column(db.String(500))
    api_secret = db.Column(db.String(500))
    base_url = db.Column(db.String(255))
    
    # Configuration
    config_data = db.Column(db.JSON)  # Store integration-specific config
    
    # Status
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')  # pending, success, error
    error_message = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization (excluding sensitive data)"""
        return {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active,
            'base_url': self.base_url,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'sync_status': self.sync_status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
