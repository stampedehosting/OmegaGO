"""
Courses API Blueprint
Handles online training courses and progress tracking
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime
import logging

from app import db
from app.models import Course, CourseEnrollment, Agent, User
from app.utils.decorators import admin_required, agent_or_admin_required

logger = logging.getLogger(__name__)

courses_bp = Blueprint('courses', __name__)

@courses_bp.route('', methods=['GET'])
@jwt_required()
def get_courses():
    """Get all available courses"""
    try:
        # Get query parameters
        category = request.args.get('category')
        difficulty = request.args.get('difficulty')
        is_required = request.args.get('is_required', type=bool)
        is_active = request.args.get('is_active', True, type=bool)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Build query
        query = Course.query.filter_by(is_active=is_active)
        
        if category:
            query = query.filter_by(category=category)
        if difficulty:
            query = query.filter_by(difficulty_level=difficulty)
        if is_required is not None:
            query = query.filter_by(is_required=is_required)
        
        # Paginate results
        courses = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get current user's enrollment status for each course
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        course_list = []
        for course in courses.items:
            course_data = course.to_dict()
            
            # Add enrollment status if user is an agent
            if user and user.agent_profile:
                enrollment = CourseEnrollment.query.filter_by(
                    agent_id=user.agent_profile.id,
                    course_id=course.id
                ).first()
                
                if enrollment:
                    course_data['enrollment'] = enrollment.to_dict()
                else:
                    course_data['enrollment'] = None
            
            course_list.append(course_data)
        
        return jsonify({
            'courses': course_list,
            'total': courses.total,
            'pages': courses.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        logger.error(f"Get courses error: {e}")
        return jsonify({'error': 'Failed to get courses'}), 500

@courses_bp.route('', methods=['POST'])
@jwt_required()
@admin_required
def create_course():
    """Create a new course (admin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'description', 'category']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create course
        course = Course(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            difficulty_level=data.get('difficulty_level', 'beginner'),
            duration_minutes=data.get('duration_minutes'),
            is_required=data.get('is_required', False),
            video_url=data.get('video_url'),
            materials_url=data.get('materials_url'),
            quiz_questions=data.get('quiz_questions', [])
        )
        
        db.session.add(course)
        db.session.commit()
        
        logger.info(f"New course created: {course.title}")
        
        return jsonify({
            'message': 'Course created successfully',
            'course': course.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Create course error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create course'}), 500

@courses_bp.route('/<int:course_id>', methods=['GET'])
@jwt_required()
def get_course(course_id):
    """Get specific course details"""
    try:
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if not course.is_active:
            return jsonify({'error': 'Course is not available'}), 404
        
        course_data = course.to_dict()
        
        # Get current user's enrollment status
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if user and user.agent_profile:
            enrollment = CourseEnrollment.query.filter_by(
                agent_id=user.agent_profile.id,
                course_id=course.id
            ).first()
            
            if enrollment:
                course_data['enrollment'] = enrollment.to_dict()
        
        return jsonify(course_data), 200
        
    except Exception as e:
        logger.error(f"Get course error: {e}")
        return jsonify({'error': 'Failed to get course'}), 500

@courses_bp.route('/<int:course_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_course(course_id):
    """Update course details (admin only)"""
    try:
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        data = request.get_json()
        
        # Update allowed fields
        allowed_fields = [
            'title', 'description', 'category', 'difficulty_level',
            'duration_minutes', 'is_required', 'is_active',
            'video_url', 'materials_url', 'quiz_questions'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(course, field, data[field])
        
        course.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Course updated: {course.title}")
        
        return jsonify({
            'message': 'Course updated successfully',
            'course': course.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Update course error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update course'}), 500

@courses_bp.route('/<int:course_id>/enroll', methods=['POST'])
@jwt_required()
def enroll_in_course(course_id):
    """Enroll current user in a course"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile not found'}), 404
        
        course = Course.query.get(course_id)
        
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        
        if not course.is_active:
            return jsonify({'error': 'Course is not available'}), 404
        
        # Check if already enrolled
        existing_enrollment = CourseEnrollment.query.filter_by(
            agent_id=user.agent_profile.id,
            course_id=course.id
        ).first()
        
        if existing_enrollment:
            return jsonify({'error': 'Already enrolled in this course'}), 409
        
        # Create enrollment
        enrollment = CourseEnrollment(
            agent_id=user.agent_profile.id,
            course_id=course.id,
            status='enrolled'
        )
        
        db.session.add(enrollment)
        db.session.commit()
        
        logger.info(f"Agent {user.agent_profile.agent_id} enrolled in course {course.title}")
        
        return jsonify({
            'message': 'Successfully enrolled in course',
            'enrollment': enrollment.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Course enrollment error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to enroll in course'}), 500

@courses_bp.route('/<int:course_id>/start', methods=['POST'])
@jwt_required()
def start_course(course_id):
    """Start a course (mark as in progress)"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile not found'}), 404
        
        enrollment = CourseEnrollment.query.filter_by(
            agent_id=user.agent_profile.id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 404
        
        if enrollment.status == 'completed':
            return jsonify({'error': 'Course already completed'}), 409
        
        # Update enrollment status
        enrollment.status = 'in_progress'
        enrollment.started_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Course started successfully',
            'enrollment': enrollment.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Start course error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to start course'}), 500

@courses_bp.route('/<int:course_id>/progress', methods=['POST'])
@jwt_required()
def update_course_progress(course_id):
    """Update course progress"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile not found'}), 404
        
        enrollment = CourseEnrollment.query.filter_by(
            agent_id=user.agent_profile.id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 404
        
        data = request.get_json()
        
        # Update progress
        if 'progress_percentage' in data:
            progress = min(max(data['progress_percentage'], 0), 100)  # Clamp between 0-100
            enrollment.progress_percentage = progress
        
        if 'time_spent_minutes' in data:
            enrollment.time_spent_minutes += data['time_spent_minutes']
        
        # Auto-start course if not started
        if enrollment.status == 'enrolled':
            enrollment.status = 'in_progress'
            enrollment.started_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Progress updated successfully',
            'enrollment': enrollment.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Update course progress error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update progress'}), 500

@courses_bp.route('/<int:course_id>/complete', methods=['POST'])
@jwt_required()
def complete_course(course_id):
    """Complete a course and submit quiz results"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile not found'}), 404
        
        enrollment = CourseEnrollment.query.filter_by(
            agent_id=user.agent_profile.id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            return jsonify({'error': 'Not enrolled in this course'}), 404
        
        if enrollment.status == 'completed':
            return jsonify({'error': 'Course already completed'}), 409
        
        data = request.get_json()
        
        # Process quiz results if provided
        quiz_score = None
        if 'quiz_answers' in data:
            course = Course.query.get(course_id)
            if course and course.quiz_questions:
                quiz_score = calculate_quiz_score(course.quiz_questions, data['quiz_answers'])
                enrollment.quiz_score = quiz_score
                enrollment.quiz_attempts += 1
        
        # Check if passing score is met (if required)
        passing_score = 70  # Default passing score
        if quiz_score is not None and quiz_score < passing_score:
            enrollment.status = 'failed'
            db.session.commit()
            
            return jsonify({
                'message': 'Course failed - quiz score below passing threshold',
                'quiz_score': quiz_score,
                'passing_score': passing_score,
                'enrollment': enrollment.to_dict()
            }), 200
        
        # Mark as completed
        enrollment.status = 'completed'
        enrollment.completed_at = datetime.utcnow()
        enrollment.progress_percentage = 100
        
        db.session.commit()
        
        logger.info(f"Agent {user.agent_profile.agent_id} completed course {course_id}")
        
        return jsonify({
            'message': 'Course completed successfully',
            'quiz_score': quiz_score,
            'enrollment': enrollment.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Complete course error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to complete course'}), 500

@courses_bp.route('/my-courses', methods=['GET'])
@jwt_required()
def get_my_courses():
    """Get current user's enrolled courses"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile not found'}), 404
        
        # Get query parameters
        status = request.args.get('status')  # enrolled, in_progress, completed, failed
        
        query = CourseEnrollment.query.filter_by(agent_id=user.agent_profile.id)
        
        if status:
            query = query.filter_by(status=status)
        
        enrollments = query.order_by(CourseEnrollment.enrolled_at.desc()).all()
        
        # Include course details with each enrollment
        course_enrollments = []
        for enrollment in enrollments:
            enrollment_data = enrollment.to_dict()
            enrollment_data['course'] = enrollment.course.to_dict()
            course_enrollments.append(enrollment_data)
        
        return jsonify({
            'enrollments': course_enrollments,
            'count': len(course_enrollments)
        }), 200
        
    except Exception as e:
        logger.error(f"Get my courses error: {e}")
        return jsonify({'error': 'Failed to get enrolled courses'}), 500

@courses_bp.route('/categories', methods=['GET'])
@jwt_required()
def get_course_categories():
    """Get all available course categories"""
    try:
        categories = db.session.query(Course.category).distinct().filter(
            Course.is_active == True
        ).all()
        
        category_list = [cat[0] for cat in categories if cat[0]]
        
        return jsonify({
            'categories': category_list
        }), 200
        
    except Exception as e:
        logger.error(f"Get course categories error: {e}")
        return jsonify({'error': 'Failed to get categories'}), 500

@courses_bp.route('/bulk-enroll', methods=['POST'])
@jwt_required()
@admin_required
def bulk_enroll_agents():
    """Bulk enroll agents in courses (admin only)"""
    try:
        data = request.get_json()
        
        agent_ids = data.get('agent_ids', [])
        course_ids = data.get('course_ids', [])
        
        if not agent_ids or not course_ids:
            return jsonify({'error': 'Agent IDs and Course IDs are required'}), 400
        
        # Validate agents and courses exist
        agents = Agent.query.filter(Agent.id.in_(agent_ids)).all()
        courses = Course.query.filter(Course.id.in_(course_ids)).all()
        
        if len(agents) != len(agent_ids):
            return jsonify({'error': 'Some agents not found'}), 404
        
        if len(courses) != len(course_ids):
            return jsonify({'error': 'Some courses not found'}), 404
        
        enrollments_created = 0
        enrollments_skipped = 0
        
        for agent in agents:
            for course in courses:
                # Check if already enrolled
                existing = CourseEnrollment.query.filter_by(
                    agent_id=agent.id,
                    course_id=course.id
                ).first()
                
                if not existing:
                    enrollment = CourseEnrollment(
                        agent_id=agent.id,
                        course_id=course.id,
                        status='enrolled'
                    )
                    db.session.add(enrollment)
                    enrollments_created += 1
                else:
                    enrollments_skipped += 1
        
        db.session.commit()
        
        logger.info(f"Bulk enrollment completed: {enrollments_created} created, {enrollments_skipped} skipped")
        
        return jsonify({
            'message': 'Bulk enrollment completed',
            'enrollments_created': enrollments_created,
            'enrollments_skipped': enrollments_skipped
        }), 200
        
    except Exception as e:
        logger.error(f"Bulk enroll error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to bulk enroll agents'}), 500

def calculate_quiz_score(quiz_questions, user_answers):
    """Calculate quiz score based on correct answers"""
    if not quiz_questions or not user_answers:
        return 0
    
    correct_answers = 0
    total_questions = len(quiz_questions)
    
    for i, question in enumerate(quiz_questions):
        question_id = question.get('id', i)
        correct_answer = question.get('correct_answer')
        user_answer = user_answers.get(str(question_id))
        
        if user_answer == correct_answer:
            correct_answers += 1
    
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0
