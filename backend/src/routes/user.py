from flask import Blueprint, jsonify, request
from src.models.models import User, db
from datetime import datetime

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
def get_users():
    """Get all users (admin only)"""
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['email', 'username']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        
        user = User(
            email=data['email'],
            username=data['username'],
            company_name=data.get('company_name'),
            phone=data.get('phone'),
            address=data.get('address'),
            supabase_user_id=data.get('supabase_user_id')
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify(user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user"""
    try:
        user = User.query.get_or_404(user_id)
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/by-email/<email>', methods=['GET'])
def get_user_by_email(email):
    """Get user by email"""
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/by-supabase-id/<supabase_id>', methods=['GET'])
def get_user_by_supabase_id(supabase_id):
    """Get user by Supabase user ID"""
    try:
        user = User.query.filter_by(supabase_user_id=supabase_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a user"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        
        # Update fields
        updatable_fields = ['username', 'company_name', 'phone', 'address']
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user"""
    try:
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/<int:user_id>/increment-quotes', methods=['POST'])
def increment_user_quotes(user_id):
    """Increment user's monthly quote counter"""
    try:
        user = User.query.get_or_404(user_id)
        user.quotes_this_month += 1
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'quotes_this_month': user.quotes_this_month,
            'can_create_more': user.is_premium or user.quotes_this_month < 3
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/users/<int:user_id>/reset-monthly-quotes', methods=['POST'])
def reset_monthly_quotes(user_id):
    """Reset user's monthly quote counter (admin only)"""
    try:
        user = User.query.get_or_404(user_id)
        user.quotes_this_month = 0
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Monthly quotes reset', 'quotes_this_month': 0})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

