"""
Agents API Blueprint
Handles agent management, profiles, and performance tracking
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, date
import logging

from app import db
from app.models import User, Agent, Sale, CourseEnrollment
from app.integrations.medicarepro import MedicareProAPI
from app.integrations.agent_methods import AgentMethodsAPI
from app.utils.decorators import admin_required, agent_or_admin_required

logger = logging.getLogger(__name__)

agents_bp = Blueprint('agents', __name__)

@agents_bp.route('', methods=['GET'])
@jwt_required()
@admin_required
def get_agents():
    """Get all agents with filtering and pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        territory = request.args.get('territory')
        status = request.args.get('status', 'active')
        
        query = Agent.query.join(User)
        
        # Apply filters
        if territory:
            query = query.filter(Agent.territory.ilike(f'%{territory}%'))
        
        if status == 'active':
            query = query.filter(User.is_active == True)
        elif status == 'inactive':
            query = query.filter(User.is_active == False)
        
        agents = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        agent_list = []
        for agent in agents.items:
            agent_data = agent.to_dict()
            agent_data['user'] = agent.user.to_dict()
            agent_list.append(agent_data)
        
        return jsonify({
            'agents': agent_list,
            'total': agents.total,
            'pages': agents.pages,
            'current_page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        logger.error(f"Get agents error: {e}")
        return jsonify({'error': 'Failed to get agents'}), 500

@agents_bp.route('', methods=['POST'])
@jwt_required()
@admin_required
def create_agent():
    """Create a new agent profile"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'agent_id', 'license_number', 'license_state']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user exists and is not already an agent
        user = User.query.get(data['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user.agent_profile:
            return jsonify({'error': 'User already has an agent profile'}), 409
        
        # Check if agent_id is unique
        if Agent.query.filter_by(agent_id=data['agent_id']).first():
            return jsonify({'error': 'Agent ID already exists'}), 409
        
        # Create agent profile
        agent = Agent(
            user_id=data['user_id'],
            agent_id=data['agent_id'],
            phone=data.get('phone'),
            license_number=data['license_number'],
            license_state=data['license_state'],
            hire_date=datetime.strptime(data['hire_date'], '%Y-%m-%d').date() if data.get('hire_date') else None,
            territory=data.get('territory'),
            commission_rate=data.get('commission_rate', 0.0),
            monthly_goal=data.get('monthly_goal', 0.0)
        )
        
        db.session.add(agent)
        
        # Update user role to agent if not already
        if user.role != 'agent':
            user.role = 'agent'
        
        db.session.commit()
        
        # Initialize integrations
        try:
            # Create agent website through Agent Methods
            agent_methods = AgentMethodsAPI()
            website_result = agent_methods.create_agent_website({
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': agent.phone,
                'license_number': agent.license_number,
                'license_state': agent.license_state,
                'territory': agent.territory
            })
            
            agent.website_url = website_result.get('website_url')
            agent.agent_methods_id = website_result.get('website_id')
            
        except Exception as integration_error:
            logger.warning(f"Failed to create agent website: {integration_error}")
        
        db.session.commit()
        
        logger.info(f"New agent created: {agent.agent_id}")
        
        agent_data = agent.to_dict()
        agent_data['user'] = user.to_dict()
        
        return jsonify({
            'message': 'Agent created successfully',
            'agent': agent_data
        }), 201
        
    except Exception as e:
        logger.error(f"Create agent error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create agent'}), 500

@agents_bp.route('/<int:agent_id>', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_agent(agent_id):
    """Get specific agent details"""
    try:
        agent = Agent.query.get(agent_id)
        
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Check if current user can access this agent
        current_user_id = get_jwt_identity()
        current_user_claims = get_jwt()
        
        if (current_user_claims.get('role') != 'admin' and 
            agent.user_id != current_user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        agent_data = agent.to_dict()
        agent_data['user'] = agent.user.to_dict()
        
        # Include recent performance data
        agent_data['recent_sales'] = [sale.to_dict() for sale in agent.sales[-10:]]
        agent_data['course_progress'] = [enrollment.to_dict() for enrollment in agent.course_enrollments]
        
        return jsonify(agent_data), 200
        
    except Exception as e:
        logger.error(f"Get agent error: {e}")
        return jsonify({'error': 'Failed to get agent'}), 500

@agents_bp.route('/<int:agent_id>', methods=['PUT'])
@jwt_required()
@agent_or_admin_required
def update_agent(agent_id):
    """Update agent profile"""
    try:
        agent = Agent.query.get(agent_id)
        
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Check permissions
        current_user_id = get_jwt_identity()
        current_user_claims = get_jwt()
        
        if (current_user_claims.get('role') != 'admin' and 
            agent.user_id != current_user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        # Update allowed fields
        allowed_fields = [
            'phone', 'territory', 'monthly_goal', 'website_template'
        ]
        
        # Admin can update additional fields
        if current_user_claims.get('role') == 'admin':
            allowed_fields.extend([
                'license_number', 'license_state', 'commission_rate',
                'hire_date'
            ])
        
        for field in allowed_fields:
            if field in data:
                if field == 'hire_date' and data[field]:
                    setattr(agent, field, datetime.strptime(data[field], '%Y-%m-%d').date())
                else:
                    setattr(agent, field, data[field])
        
        agent.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Agent updated: {agent.agent_id}")
        
        return jsonify({
            'message': 'Agent updated successfully',
            'agent': agent.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Update agent error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update agent'}), 500

@agents_bp.route('/<int:agent_id>/performance', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_agent_performance(agent_id):
    """Get agent performance metrics"""
    try:
        agent = Agent.query.get(agent_id)
        
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Check permissions
        current_user_id = get_jwt_identity()
        current_user_claims = get_jwt()
        
        if (current_user_claims.get('role') != 'admin' and 
            agent.user_id != current_user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get performance period
        period = request.args.get('period', 'month')  # month, quarter, year
        
        # Calculate date range
        today = date.today()
        if period == 'month':
            start_date = today.replace(day=1)
        elif period == 'quarter':
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=quarter_start_month, day=1)
        else:  # year
            start_date = today.replace(month=1, day=1)
        
        # Get sales data for the period
        sales = Sale.query.filter(
            Sale.agent_id == agent_id,
            Sale.sale_date >= start_date,
            Sale.sale_date <= today
        ).all()
        
        # Calculate metrics
        total_sales = sum(sale.premium_amount for sale in sales)
        total_commissions = sum(sale.commission_amount for sale in sales)
        sales_count = len(sales)
        
        # Goal progress
        goal_progress = 0
        if agent.monthly_goal > 0:
            if period == 'month':
                goal_progress = (total_commissions / agent.monthly_goal) * 100
            elif period == 'quarter':
                goal_progress = (total_commissions / (agent.monthly_goal * 3)) * 100
            else:  # year
                goal_progress = (total_commissions / (agent.monthly_goal * 12)) * 100
        
        # Training progress
        completed_courses = CourseEnrollment.query.filter(
            CourseEnrollment.agent_id == agent_id,
            CourseEnrollment.status == 'completed'
        ).count()
        
        total_courses = CourseEnrollment.query.filter(
            CourseEnrollment.agent_id == agent_id
        ).count()
        
        training_progress = (completed_courses / total_courses * 100) if total_courses > 0 else 0
        
        performance_data = {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': today.isoformat(),
            'sales_metrics': {
                'total_sales': total_sales,
                'total_commissions': total_commissions,
                'sales_count': sales_count,
                'average_sale': total_sales / sales_count if sales_count > 0 else 0,
                'goal_progress': min(goal_progress, 100)  # Cap at 100%
            },
            'training_metrics': {
                'completed_courses': completed_courses,
                'total_courses': total_courses,
                'training_progress': training_progress
            },
            'ytd_metrics': {
                'ytd_sales': agent.ytd_sales,
                'ytd_commissions': agent.ytd_commissions
            }
        }
        
        return jsonify(performance_data), 200
        
    except Exception as e:
        logger.error(f"Get agent performance error: {e}")
        return jsonify({'error': 'Failed to get agent performance'}), 500

@agents_bp.route('/<int:agent_id>/sync', methods=['POST'])
@jwt_required()
@admin_required
def sync_agent_data(agent_id):
    """Sync agent data from external systems"""
    try:
        agent = Agent.query.get(agent_id)
        
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        sync_results = {}
        
        # Sync from MedicarePro
        if agent.medicarepro_id:
            try:
                medicarepro = MedicareProAPI()
                mp_data = medicarepro.sync_agent_data(agent.medicarepro_id)
                sync_results['medicarepro'] = {
                    'status': 'success',
                    'leads_count': len(mp_data.get('leads', [])),
                    'policies_count': len(mp_data.get('policies', [])),
                    'last_sync': datetime.now().isoformat()
                }
                
                # Update agent performance metrics from synced data
                commissions = mp_data.get('commissions', [])
                if commissions:
                    ytd_commissions = sum(c.get('amount', 0) for c in commissions)
                    agent.ytd_commissions = ytd_commissions
                
            except Exception as mp_error:
                logger.error(f"MedicarePro sync error: {mp_error}")
                sync_results['medicarepro'] = {
                    'status': 'error',
                    'error': str(mp_error)
                }
        
        # Sync from Agent Methods
        if agent.agent_methods_id:
            try:
                agent_methods = AgentMethodsAPI()
                website_analytics = agent_methods.get_website_analytics(agent.agent_methods_id)
                sync_results['agent_methods'] = {
                    'status': 'success',
                    'website_visits': website_analytics.get('visits', 0),
                    'leads_captured': website_analytics.get('leads', 0),
                    'last_sync': datetime.now().isoformat()
                }
                
            except Exception as am_error:
                logger.error(f"Agent Methods sync error: {am_error}")
                sync_results['agent_methods'] = {
                    'status': 'error',
                    'error': str(am_error)
                }
        
        agent.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Agent data sync completed',
            'sync_results': sync_results
        }), 200
        
    except Exception as e:
        logger.error(f"Sync agent data error: {e}")
        return jsonify({'error': 'Failed to sync agent data'}), 500

@agents_bp.route('/<int:agent_id>/website', methods=['POST'])
@jwt_required()
@agent_or_admin_required
def update_agent_website(agent_id):
    """Update agent website configuration"""
    try:
        agent = Agent.query.get(agent_id)
        
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Check permissions
        current_user_id = get_jwt_identity()
        current_user_claims = get_jwt()
        
        if (current_user_claims.get('role') != 'admin' and 
            agent.user_id != current_user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        
        if not agent.agent_methods_id:
            return jsonify({'error': 'Agent website not found'}), 404
        
        # Update website through Agent Methods API
        agent_methods = AgentMethodsAPI()
        update_result = agent_methods.update_agent_website(
            agent.agent_methods_id, 
            data
        )
        
        # Update local data
        if 'template' in data:
            agent.website_template = data['template']
        
        agent.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Website updated successfully',
            'website_data': update_result
        }), 200
        
    except Exception as e:
        logger.error(f"Update agent website error: {e}")
        return jsonify({'error': 'Failed to update website'}), 500

@agents_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_agent_dashboard():
    """Get dashboard data for current agent"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.agent_profile:
            return jsonify({'error': 'Agent profile not found'}), 404
        
        agent = user.agent_profile
        
        # Get recent sales (last 30 days)
        thirty_days_ago = date.today() - datetime.timedelta(days=30)
        recent_sales = Sale.query.filter(
            Sale.agent_id == agent.id,
            Sale.sale_date >= thirty_days_ago
        ).order_by(Sale.sale_date.desc()).limit(10).all()
        
        # Get course progress
        course_enrollments = CourseEnrollment.query.filter(
            CourseEnrollment.agent_id == agent.id
        ).all()
        
        # Calculate quick stats
        total_recent_sales = sum(sale.premium_amount for sale in recent_sales)
        total_recent_commissions = sum(sale.commission_amount for sale in recent_sales)
        
        completed_courses = len([e for e in course_enrollments if e.status == 'completed'])
        in_progress_courses = len([e for e in course_enrollments if e.status == 'in_progress'])
        
        dashboard_data = {
            'agent': agent.to_dict(),
            'quick_stats': {
                'recent_sales_count': len(recent_sales),
                'recent_sales_amount': total_recent_sales,
                'recent_commissions': total_recent_commissions,
                'completed_courses': completed_courses,
                'in_progress_courses': in_progress_courses,
                'goal_progress': (total_recent_commissions / agent.monthly_goal * 100) if agent.monthly_goal > 0 else 0
            },
            'recent_sales': [sale.to_dict() for sale in recent_sales],
            'course_progress': [enrollment.to_dict() for enrollment in course_enrollments[:5]]
        }
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        logger.error(f"Get agent dashboard error: {e}")
        return jsonify({'error': 'Failed to get dashboard data'}), 500
