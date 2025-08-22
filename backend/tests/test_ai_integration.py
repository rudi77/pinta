import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from src.models.models import User

class TestAIIntegration:
    """Integration tests for AI endpoints"""

    @patch('src.services.ai_service.AIService.analyze_project_requirements')
    async def test_analyze_project(self, mock_analyze, client: AsyncClient, auth_headers: dict):
        """Test project analysis endpoint"""
        mock_analyze.return_value = {
            "rooms": [
                {
                    "name": "Living Room",
                    "area": 25.5,
                    "wall_area": 45.0,
                    "paint_type": "Premium",
                    "estimated_hours": 8
                }
            ],
            "total_estimated_cost": 1200.00,
            "estimated_duration": "2-3 days",
            "recommendations": ["Use primer for better coverage"]
        }
        
        project_data = {
            "description": "Paint a 3-bedroom house living room with premium paint",
            "customer_requirements": "High-quality finish, eco-friendly paint",
            "room_dimensions": "5m x 5m x 3m height"
        }
        
        response = await client.post("/api/v1/ai/analyze-project", json=project_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "rooms" in data
        assert "total_estimated_cost" in data
        assert "estimated_duration" in data
        assert "recommendations" in data
        assert len(data["rooms"]) == 1
        assert data["total_estimated_cost"] == 1200.00

    async def test_analyze_project_unauthorized(self, client: AsyncClient):
        """Test project analysis without authentication"""
        project_data = {
            "description": "Paint a room",
            "customer_requirements": "Standard finish"
        }
        
        response = await client.post("/api/v1/ai/analyze-project", json=project_data)
        assert response.status_code == 401

    @patch('src.services.ai_service.AIService.generate_quote_suggestions')
    async def test_generate_quote_suggestions(self, mock_suggestions, client: AsyncClient, auth_headers: dict):
        """Test quote suggestions generation"""
        mock_suggestions.return_value = {
            "suggested_materials": [
                {"name": "Premium Latex Paint", "quantity": "5 gallons", "cost": 150.00},
                {"name": "Paint Primer", "quantity": "2 gallons", "cost": 60.00}
            ],
            "labor_breakdown": {
                "prep_work": 4,
                "painting": 8,
                "cleanup": 2
            },
            "alternative_options": [
                {"description": "Budget option", "cost_savings": 200.00},
                {"description": "Premium upgrade", "additional_cost": 300.00}
            ]
        }
        
        suggestion_data = {
            "rooms": [
                {
                    "name": "Living Room",
                    "area": 25.5,
                    "paint_type": "Premium"
                }
            ],
            "customer_preferences": "High-quality, durable finish",
            "budget_range": "1000-1500"
        }
        
        response = await client.post("/api/v1/ai/quote-suggestions", json=suggestion_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "suggested_materials" in data
        assert "labor_breakdown" in data
        assert "alternative_options" in data
        assert len(data["suggested_materials"]) == 2

    @patch('src.services.ai_service.AIService.optimize_quote')
    async def test_optimize_quote(self, mock_optimize, client: AsyncClient, auth_headers: dict, test_quote):
        """Test quote optimization"""
        mock_optimize.return_value = {
            "optimized_total": 1100.00,
            "savings": 150.00,
            "optimizations": [
                {
                    "category": "materials",
                    "description": "Use bulk purchase discount",
                    "savings": 100.00
                },
                {
                    "category": "labor",
                    "description": "Optimize work schedule",
                    "savings": 50.00
                }
            ],
            "efficiency_score": 0.92
        }
        
        response = await client.post(f"/api/v1/ai/optimize-quote/{test_quote.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "optimized_total" in data
        assert "savings" in data
        assert "optimizations" in data
        assert "efficiency_score" in data
        assert data["savings"] == 150.00

    async def test_optimize_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test optimizing nonexistent quote"""
        response = await client.post("/api/v1/ai/optimize-quote/99999", headers=auth_headers)
        assert response.status_code == 404

    @patch('src.services.ai_service.AIService.generate_recommendations')
    async def test_generate_recommendations(self, mock_recommendations, client: AsyncClient, auth_headers: dict):
        """Test generating AI recommendations"""
        mock_recommendations.return_value = {
            "recommendations": [
                {
                    "category": "efficiency",
                    "title": "Use spray equipment for large areas",
                    "description": "Spray painting can reduce time by 40% for walls larger than 100 sq ft",
                    "priority": "high"
                },
                {
                    "category": "quality",
                    "title": "Apply primer on new drywall",
                    "description": "Primer ensures better paint adhesion and color uniformity",
                    "priority": "medium"
                }
            ],
            "cost_impact": {
                "potential_savings": 200.00,
                "additional_costs": 50.00,
                "net_benefit": 150.00
            }
        }
        
        recommendation_data = {
            "project_type": "interior_painting",
            "room_count": 3,
            "total_area": 150.0,
            "customer_budget": 2000.00
        }
        
        response = await client.post("/api/v1/ai/recommendations", json=recommendation_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "recommendations" in data
        assert "cost_impact" in data
        assert len(data["recommendations"]) == 2

    @patch('src.services.ai_service.AIService.validate_quote_accuracy')
    async def test_validate_quote_accuracy(self, mock_validate, client: AsyncClient, auth_headers: dict, test_quote):
        """Test quote accuracy validation"""
        mock_validate.return_value = {
            "accuracy_score": 0.95,
            "validation_results": {
                "material_estimates": "accurate",
                "labor_calculations": "accurate",
                "pricing": "slightly_high"
            },
            "suggested_adjustments": [
                {
                    "field": "material_cost",
                    "current_value": 850.00,
                    "suggested_value": 800.00,
                    "reason": "Market price analysis suggests lower cost"
                }
            ],
            "confidence_level": "high"
        }
        
        response = await client.post(f"/api/v1/ai/validate-quote/{test_quote.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "accuracy_score" in data
        assert "validation_results" in data
        assert "suggested_adjustments" in data
        assert "confidence_level" in data
        assert data["accuracy_score"] == 0.95

    @patch('src.services.ai_service.AIService.analyze_document')
    async def test_analyze_document_content(self, mock_analyze_doc, client: AsyncClient, auth_headers: dict):
        """Test document content analysis"""
        mock_analyze_doc.return_value = {
            "document_type": "floor_plan",
            "extracted_measurements": {
                "rooms": [
                    {"name": "Living Room", "dimensions": "5m x 4m"},
                    {"name": "Kitchen", "dimensions": "3m x 4m"}
                ],
                "total_area": 32.0
            },
            "paint_requirements": {
                "wall_area": 80.0,
                "ceiling_area": 32.0,
                "estimated_gallons": 6
            },
            "confidence": 0.88
        }
        
        # Simulate file upload
        files = {"file": ("test_plan.pdf", b"fake pdf content", "application/pdf")}
        
        response = await client.post("/api/v1/ai/analyze-document", files=files, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "document_type" in data
        assert "extracted_measurements" in data
        assert "paint_requirements" in data
        assert "confidence" in data

    async def test_ai_endpoint_rate_limiting(self, client: AsyncClient, auth_headers: dict):
        """Test rate limiting on AI endpoints"""
        # This would test rate limiting - implementation depends on your rate limiting setup
        project_data = {
            "description": "Simple paint job",
            "customer_requirements": "Basic finish"
        }
        
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = await client.post("/api/v1/ai/analyze-project", json=project_data, headers=auth_headers)
            responses.append(response.status_code)
        
        # At least some requests should succeed (exact behavior depends on rate limit config)
        assert any(status == 200 for status in responses[:3])

    @patch('src.services.ai_service.AIService.get_market_insights')
    async def test_get_market_insights(self, mock_insights, client: AsyncClient, auth_headers: dict):
        """Test market insights endpoint"""
        mock_insights.return_value = {
            "regional_pricing": {
                "average_labor_rate": 45.00,
                "material_cost_index": 1.12,
                "market_trend": "increasing"
            },
            "seasonal_factors": {
                "current_season": "spring",
                "demand_level": "high",
                "price_adjustment": 1.05
            },
            "recommendations": [
                "Consider scheduling projects during off-peak season for better rates",
                "Material costs are expected to increase by 3% next quarter"
            ]
        }
        
        response = await client.get("/api/v1/ai/market-insights?location=general", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "regional_pricing" in data
        assert "seasonal_factors" in data
        assert "recommendations" in data