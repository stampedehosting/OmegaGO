"""
Analytics API Blueprint
Handles performance analytics, reporting, and dashboard data
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract
import logging

from app import db
from app.models import Agent, Sale, CourseEnrollment, Course, User
from app.utils.decorators import admin_required, agent_or_admin_required

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@admin_required
def get_admin_dashboard():
    """Get admin dashboard analytics"""
    try:
        # Get date range
        period = request.args.get('period', 'month')  # month, quarter, year
        
        today = date.today()
        if period == 'month':
            start_date = today.replace(day=1)
        elif period == 'quarter':
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=quarter_start_month, day=1)
        else:  # year
            start_date = today.replace(month=1, day=1)
        
        # Agent metrics
        total_agents = Agent.query.join(User).filter(User.is_active == True).count()
        new_agents = Agent.query.join(User).filter(
            User.is_active == True,
            Agent.created_at >= start_date
        ).count()
        
        # Sales metrics
        sales_query = Sale.query.filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= today
        )
        
        total_sales = sales_query.with_entities(func.sum(Sale.premium_amount)).scalar() or 0
        total_commissions = sales_query.with_entities(func.sum(Sale.commission_amount)).scalar() or 0
        sales_count = sales_query.count()
        
        # Training metrics
        total_courses = Course.query.filter_by(is_active=True).count()
        completed_enrollments = CourseEnrollment.query.filter(
            CourseEnrollment.completed_at >= start_date,
            CourseEnrollment.status == 'completed'
        ).count()
        
        # Top performing agents
        top_agents = db.session.query(
            Agent.id,
            Agent.agent_id,
            User.first_name,
            User.last_name,
            func.sum(Sale.commission_amount).label('total_commissions'),
            func.count(Sale.id).label('sales_count')
        ).join(User).join(Sale).filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= today
        ).group_by(Agent.id, Agent.agent_id, User.first_name, User.last_name)\
         .order_by(func.sum(Sale.commission_amount).desc())\
         .limit(10).all()
        
        # Monthly sales trend (last 12 months)
        twelve_months_ago = today - timedelta(days=365)
        monthly_sales = db.session.query(
            extract('year', Sale.sale_date).label('year'),
            extract('month', Sale.sale_date).label('month'),
            func.sum(Sale.premium_amount).label('total_sales'),
            func.sum(Sale.commission_amount).label('total_commissions'),
            func.count(Sale.id).label('sales_count')
        ).filter(
            Sale.sale_date >= twelve_months_ago
        ).group_by(
            extract('year', Sale.sale_date),
            extract('month', Sale.sale_date)
        ).order_by(
            extract('year', Sale.sale_date),
            extract('month', Sale.sale_date)
        ).all()
        
        # Course completion rates
        course_stats = db.session.query(
            Course.id,
            Course.title,
            Course.category,
            func.count(CourseEnrollment.id).label('total_enrollments'),
            func.sum(func.case([(CourseEnrollment.status == 'completed', 1)], else_=0)).label('completed'),
            func.sum(func.case([(CourseEnrollment.status == 'in_progress', 1)], else_=0)).label('in_progress')
        ).join(CourseEnrollment).filter(
            Course.is_active == True
        ).group_by(Course.id, Course.title, Course.category).all()
        
        dashboard_data = {
            'period': period,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': today.isoformat()
            },
            'overview': {
                'total_agents': total_agents,
                'new_agents': new_agents,
                'total_sales': float(total_sales),
                'total_commissions': float(total_commissions),
                'sales_count': sales_count,
                'average_sale': float(total_sales / sales_count) if sales_count > 0 else 0,
                'total_courses': total_courses,
                'completed_enrollments': completed_enrollments
            },
            'top_agents': [
                {
                    'agent_id': agent.agent_id,
                    'name': f"{agent.first_name} {agent.last_name}",
                    'total_commissions': float(agent.total_commissions),
                    'sales_count': agent.sales_count
                }
                for agent in top_agents
            ],
            'monthly_trends': [
                {
                    'year': int(month.year),
                    'month': int(month.month),
                    'total_sales': float(month.total_sales or 0),
                    'total_commissions': float(month.total_commissions or 0),
                    'sales_count': month.sales_count
                }
                for month in monthly_sales
            ],
            'course_stats': [
                {
                    'course_id': course.id,
                    'title': course.title,
                    'category': course.category,
                    'total_enrollments': course.total_enrollments,
                    'completed': course.completed or 0,
                    'in_progress': course.in_progress or 0,
                    'completion_rate': (course.completed / course.total_enrollments * 100) if course.total_enrollments > 0 else 0
                }
                for course in course_stats
            ]
        }
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        logger.error(f"Get admin dashboard error: {e}")
        return jsonify({'error': 'Failed to get dashboard data'}), 500

@analytics_bp.route('/agents/<int:agent_id>', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_agent_analytics(agent_id):
    """Get detailed analytics for a specific agent"""
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
        
        # Get date range
        period = request.args.get('period', 'month')
        
        today = date.today()
        if period == 'month':
            start_date = today.replace(day=1)
        elif period == 'quarter':
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=quarter_start_month, day=1)
        else:  # year
            start_date = today.replace(month=1, day=1)
        
        # Sales analytics
        sales = Sale.query.filter(
            Sale.agent_id == agent_id,
            Sale.sale_date >= start_date,
            Sale.sale_date <= today
        ).all()
        
        total_sales = sum(sale.premium_amount for sale in sales)
        total_commissions = sum(sale.commission_amount for sale in sales)
        sales_count = len(sales)
        
        # Daily sales trend (last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        daily_sales = db.session.query(
            Sale.sale_date,
            func.sum(Sale.premium_amount).label('daily_sales'),
            func.sum(Sale.commission_amount).label('daily_commissions'),
            func.count(Sale.id).label('daily_count')
        ).filter(
            Sale.agent_id == agent_id,
            Sale.sale_date >= thirty_days_ago
        ).group_by(Sale.sale_date).order_by(Sale.sale_date).all()
        
        # Training progress
        enrollments = CourseEnrollment.query.filter_by(agent_id=agent_id).all()
        completed_courses = [e for e in enrollments if e.status == 'completed']
        in_progress_courses = [e for e in enrollments if e.status == 'in_progress']
        
        # Goal progress
        goal_progress = 0
        if agent.monthly_goal > 0:
            if period == 'month':
                goal_progress = (total_commissions / agent.monthly_goal) * 100
            elif period == 'quarter':
                goal_progress = (total_commissions / (agent.monthly_goal * 3)) * 100
            else:  # year
                goal_progress = (total_commissions / (agent.monthly_goal * 12)) * 100
        
        # Sales by customer (top 10)
        top_customers = db.session.query(
            Sale.customer_name,
            func.sum(Sale.premium_amount).label('total_premium'),
            func.sum(Sale.commission_amount).label('total_commission'),
            func.count(Sale.id).label('policy_count')
        ).filter(
            Sale.agent_id == agent_id,
            Sale.sale_date >= start_date
        ).group_by(Sale.customer_name)\
         .order_by(func.sum(Sale.commission_amount).desc())\
         .limit(10).all()
        
        analytics_data = {
            'agent': agent.to_dict(),
            'period': period,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': today.isoformat()
            },
            'sales_metrics': {
                'total_sales': total_sales,
                'total_commissions': total_commissions,
                'sales_count': sales_count,
                'average_sale': total_sales / sales_count if sales_count > 0 else 0,
                'goal_progress': min(goal_progress, 100)
            },
            'training_metrics': {
                'total_enrollments': len(enrollments),
                'completed_courses': len(completed_courses),
                'in_progress_courses': len(in_progress_courses),
                'completion_rate': (len(completed_courses) / len(enrollments) * 100) if enrollments else 0
            },
            'daily_trends': [
                {
                    'date': day.sale_date.isoformat(),
                    'sales': float(day.daily_sales or 0),
                    'commissions': float(day.daily_commissions or 0),
                    'count': day.daily_count
                }
                for day in daily_sales
            ],
            'top_customers': [
                {
                    'customer_name': customer.customer_name,
                    'total_premium': float(customer.total_premium),
                    'total_commission': float(customer.total_commission),
                    'policy_count': customer.policy_count
                }
                for customer in top_customers
            ],
            'recent_sales': [sale.to_dict() for sale in sales[-10:]],
            'course_progress': [enrollment.to_dict() for enrollment in enrollments]
        }
        
        return jsonify(analytics_data), 200
        
    except Exception as e:
        logger.error(f"Get agent analytics error: {e}")
        return jsonify({'error': 'Failed to get agent analytics'}), 500

@analytics_bp.route('/revenue', methods=['GET'])
@jwt_required()
@admin_required
def get_revenue_analytics():
    """Get revenue analytics and forecasting"""
    try:
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            # Default to current year
            today = date.today()
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Revenue by month
        monthly_revenue = db.session.query(
            extract('year', Sale.sale_date).label('year'),
            extract('month', Sale.sale_date).label('month'),
            func.sum(Sale.premium_amount).label('total_premium'),
            func.sum(Sale.commission_amount).label('total_commission'),
            func.count(Sale.id).label('sales_count'),
            func.avg(Sale.premium_amount).label('avg_premium')
        ).filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= end_date
        ).group_by(
            extract('year', Sale.sale_date),
            extract('month', Sale.sale_date)
        ).order_by(
            extract('year', Sale.sale_date),
            extract('month', Sale.sale_date)
        ).all()
        
        # Revenue by agent
        agent_revenue = db.session.query(
            Agent.id,
            Agent.agent_id,
            User.first_name,
            User.last_name,
            func.sum(Sale.premium_amount).label('total_premium'),
            func.sum(Sale.commission_amount).label('total_commission'),
            func.count(Sale.id).label('sales_count')
        ).join(User).join(Sale).filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= end_date
        ).group_by(
            Agent.id, Agent.agent_id, User.first_name, User.last_name
        ).order_by(func.sum(Sale.commission_amount).desc()).all()
        
        # Revenue by territory
        territory_revenue = db.session.query(
            Agent.territory,
            func.sum(Sale.premium_amount).label('total_premium'),
            func.sum(Sale.commission_amount).label('total_commission'),
            func.count(Sale.id).label('sales_count'),
            func.count(func.distinct(Agent.id)).label('agent_count')
        ).join(Sale).filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= end_date,
            Agent.territory.isnot(None)
        ).group_by(Agent.territory)\
         .order_by(func.sum(Sale.commission_amount).desc()).all()
        
        # Calculate totals
        total_premium = sum(month.total_premium or 0 for month in monthly_revenue)
        total_commission = sum(month.total_commission or 0 for month in monthly_revenue)
        total_sales = sum(month.sales_count for month in monthly_revenue)
        
        # Simple forecasting (linear trend)
        if len(monthly_revenue) >= 3:
            recent_months = monthly_revenue[-3:]
            avg_monthly_commission = sum(m.total_commission or 0 for m in recent_months) / len(recent_months)
            projected_next_month = avg_monthly_commission * 1.05  # 5% growth assumption
        else:
            projected_next_month = 0
        
        revenue_data = {
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_premium': float(total_premium),
                'total_commission': float(total_commission),
                'total_sales': total_sales,
                'average_premium': float(total_premium / total_sales) if total_sales > 0 else 0,
                'commission_rate': float(total_commission / total_premium * 100) if total_premium > 0 else 0
            },
            'monthly_trends': [
                {
                    'year': int(month.year),
                    'month': int(month.month),
                    'total_premium': float(month.total_premium or 0),
                    'total_commission': float(month.total_commission or 0),
                    'sales_count': month.sales_count,
                    'avg_premium': float(month.avg_premium or 0)
                }
                for month in monthly_revenue
            ],
            'agent_performance': [
                {
                    'agent_id': agent.agent_id,
                    'name': f"{agent.first_name} {agent.last_name}",
                    'total_premium': float(agent.total_premium),
                    'total_commission': float(agent.total_commission),
                    'sales_count': agent.sales_count,
                    'avg_commission_per_sale': float(agent.total_commission / agent.sales_count) if agent.sales_count > 0 else 0
                }
                for agent in agent_revenue
            ],
            'territory_performance': [
                {
                    'territory': territory.territory,
                    'total_premium': float(territory.total_premium),
                    'total_commission': float(territory.total_commission),
                    'sales_count': territory.sales_count,
                    'agent_count': territory.agent_count,
                    'avg_commission_per_agent': float(territory.total_commission / territory.agent_count) if territory.agent_count > 0 else 0
                }
                for territory in territory_revenue
            ],
            'forecast': {
                'projected_next_month_commission': float(projected_next_month)
            }
        }
        
        return jsonify(revenue_data), 200
        
    except Exception as e:
        logger.error(f"Get revenue analytics error: {e}")
        return jsonify({'error': 'Failed to get revenue analytics'}), 500

@analytics_bp.route('/training', methods=['GET'])
@jwt_required()
@admin_required
def get_training_analytics():
    """Get training and course completion analytics"""
    try:
        # Course completion statistics
        course_stats = db.session.query(
            Course.id,
            Course.title,
            Course.category,
            Course.difficulty_level,
            Course.is_required,
            func.count(CourseEnrollment.id).label('total_enrollments'),
            func.sum(func.case([(CourseEnrollment.status == 'completed', 1)], else_=0)).label('completed'),
            func.sum(func.case([(CourseEnrollment.status == 'in_progress', 1)], else_=0)).label('in_progress'),
            func.sum(func.case([(CourseEnrollment.status == 'failed', 1)], else_=0)).label('failed'),
            func.avg(CourseEnrollment.quiz_score).label('avg_quiz_score'),
            func.avg(CourseEnrollment.time_spent_minutes).label('avg_time_spent')
        ).join(CourseEnrollment).filter(
            Course.is_active == True
        ).group_by(
            Course.id, Course.title, Course.category, 
            Course.difficulty_level, Course.is_required
        ).all()
        
        # Agent training progress
        agent_progress = db.session.query(
            Agent.id,
            Agent.agent_id,
            User.first_name,
            User.last_name,
            func.count(CourseEnrollment.id).label('total_enrollments'),
            func.sum(func.case([(CourseEnrollment.status == 'completed', 1)], else_=0)).label('completed'),
            func.avg(CourseEnrollment.quiz_score).label('avg_quiz_score')
        ).join(User).join(CourseEnrollment).group_by(
            Agent.id, Agent.agent_id, User.first_name, User.last_name
        ).order_by(func.sum(func.case([(CourseEnrollment.status == 'completed', 1)], else_=0)).desc()).all()
        
        # Training completion trends (last 6 months)
        six_months_ago = date.today() - timedelta(days=180)
        completion_trends = db.session.query(
            extract('year', CourseEnrollment.completed_at).label('year'),
            extract('month', CourseEnrollment.completed_at).label('month'),
            func.count(CourseEnrollment.id).label('completions')
        ).filter(
            CourseEnrollment.completed_at >= six_months_ago,
            CourseEnrollment.status == 'completed'
        ).group_by(
            extract('year', CourseEnrollment.completed_at),
            extract('month', CourseEnrollment.completed_at)
        ).order_by(
            extract('year', CourseEnrollment.completed_at),
            extract('month', CourseEnrollment.completed_at)
        ).all()
        
        training_data = {
            'course_statistics': [
                {
                    'course_id': course.id,
                    'title': course.title,
                    'category': course.category,
                    'difficulty_level': course.difficulty_level,
                    'is_required': course.is_required,
                    'total_enrollments': course.total_enrollments,
                    'completed': course.completed or 0,
                    'in_progress': course.in_progress or 0,
                    'failed': course.failed or 0,
                    'completion_rate': (course.completed / course.total_enrollments * 100) if course.total_enrollments > 0 else 0,
                    'avg_quiz_score': float(course.avg_quiz_score or 0),
                    'avg_time_spent': float(course.avg_time_spent or 0)
                }
                for course in course_stats
            ],
            'agent_progress': [
                {
                    'agent_id': agent.agent_id,
                    'name': f"{agent.first_name} {agent.last_name}",
                    'total_enrollments': agent.total_enrollments,
                    'completed': agent.completed or 0,
                    'completion_rate': (agent.completed / agent.total_enrollments * 100) if agent.total_enrollments > 0 else 0,
                    'avg_quiz_score': float(agent.avg_quiz_score or 0)
                }
                for agent in agent_progress
            ],
            'completion_trends': [
                {
                    'year': int(trend.year),
                    'month': int(trend.month),
                    'completions': trend.completions
                }
                for trend in completion_trends
            ]
        }
        
        return jsonify(training_data), 200
        
    except Exception as e:
        logger.error(f"Get training analytics error: {e}")
        return jsonify({'error': 'Failed to get training analytics'}), 500

@analytics_bp.route('/export', methods=['POST'])
@jwt_required()
@admin_required
def export_analytics():
    """Export analytics data to CSV/Excel format"""
    try:
        data = request.get_json()
        
        export_type = data.get('type', 'sales')  # sales, agents, training
        format_type = data.get('format', 'csv')  # csv, excel
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # This would implement actual export functionality
        # For now, return a placeholder response
        
        return jsonify({
            'message': 'Export functionality not yet implemented',
            'export_type': export_type,
            'format': format_type,
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Export analytics error: {e}")
        return jsonify({'error': 'Failed to export analytics'}), 500
