import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import websockets
import json

# Remove main import to avoid table conflicts
from src.core.cache import cache_service
from src.core.background_tasks import background_task_manager
from src.services.ai_service import AIService

@pytest.fixture
def client():
    # Create minimal FastAPI app for testing
    from fastapi import FastAPI
    test_app = FastAPI()
    return TestClient(test_app)

@pytest.mark.asyncio
async def test_cache_performance():
    """Test Redis cache performance"""
    
    # Connect to cache
    await cache_service.connect()
    
    if not cache_service.enabled:
        pytest.skip("Redis not available")
    
    user_id = 123
    conversation_id = "test_conv"
    
    # Test write performance
    start_time = time.time()
    
    for i in range(100):
        await cache_service.append_to_conversation(
            user_id, 
            {"role": "user", "content": f"Message {i}"},
            conversation_id
        )
    
    write_time = time.time() - start_time
    
    # Test read performance
    start_time = time.time()
    
    for i in range(100):
        history = await cache_service.get_conversation_history(user_id, conversation_id)
    
    read_time = time.time() - start_time
    
    # Cleanup
    await cache_service.clear_conversation(user_id, conversation_id)
    
    # Performance assertions (should complete within reasonable time)
    assert write_time < 2.0, f"Cache write too slow: {write_time:.2f}s"
    assert read_time < 1.0, f"Cache read too slow: {read_time:.2f}s"
    assert len(history) == 100, "Not all messages cached"

@pytest.mark.asyncio
async def test_background_task_performance():
    """Test background task processing speed"""
    
    # Mock AI service for performance testing
    with patch.object(AIService, 'process_answers_and_generate_quote') as mock_ai:
        mock_ai.return_value = {
            "quote": {
                "project_title": "Test Project",
                "total_amount": 1000.0,
                "labor_hours": 10.0,
                "hourly_rate": 50.0,
                "material_cost": 500.0,
                "additional_costs": 0.0
            },
            "items": [
                {
                    "description": "Test Item",
                    "quantity": 1,
                    "unit": "pcs",
                    "unit_price": 100.0,
                    "total_price": 100.0,
                    "category": "labor"
                }
            ]
        }
        
        project_data = {
            "description": "Test project",
            "customer_name": "Test Customer"
        }
        answers = [{"question": "test", "answer": "test"}]
        
        # Measure task start time
        start_time = time.time()
        
        task_id = await background_task_manager.start_quote_generation_task(
            user_id=1,
            project_data=project_data,
            answers=answers
        )
        
        task_start_time = time.time() - start_time
        
        # Wait for task completion with timeout
        timeout = 30
        start_wait = time.time()
        
        while time.time() - start_wait < timeout:
            status = await background_task_manager.get_task_status(task_id)
            if status and status.get("status") == "completed":
                break
            await asyncio.sleep(0.1)
        
        total_time = time.time() - start_time
        
        # Performance assertions
        assert task_start_time < 0.5, f"Task start too slow: {task_start_time:.2f}s"
        assert total_time < 5.0, f"Task completion too slow: {total_time:.2f}s"
        
        final_status = await background_task_manager.get_task_status(task_id)
        assert final_status["status"] == "completed"

def test_api_response_time(client):
    """Test API endpoint response times"""
    
    # Mock authentication
    with patch('src.core.security.get_current_user') as mock_user:
        mock_user.return_value = MagicMock(
            id=1,
            email="test@example.com",
            is_premium=False,
            quotes_this_month=0,
            additional_quotes=0
        )
        
        # Test health endpoint
        start_time = time.time()
        response = client.get("/health")
        health_time = time.time() - start_time
        
        assert response.status_code == 200
        assert health_time < 0.1, f"Health check too slow: {health_time:.3f}s"
        
        # Test WebSocket health endpoint
        start_time = time.time()
        response = client.get("/ws-health")
        ws_health_time = time.time() - start_time
        
        assert response.status_code == 200
        assert ws_health_time < 0.1, f"WebSocket health check too slow: {ws_health_time:.3f}s"

@pytest.mark.asyncio
async def test_streaming_response_performance():
    """Test AI streaming response performance"""
    
    ai_service = AIService()
    
    # Mock OpenAI streaming response
    class MockStreamChunk:
        def __init__(self, content):
            self.choices = [MagicMock(delta=MagicMock(content=content))]
    
    async def mock_stream():
        chunks = ["This ", "is ", "a ", "streaming ", "response ", "test."]
        for chunk in chunks:
            yield MockStreamChunk(chunk)
        yield MockStreamChunk(None)  # End of stream
    
    with patch.object(ai_service.client.chat.completions, 'create') as mock_create:
        mock_create.return_value = mock_stream()
        
        start_time = time.time()
        
        response_parts = []
        async for chunk in ai_service.ask_follow_up_question_stream(
            conversation_history=[],
            user_message="Test question"
        ):
            if chunk.get("type") == "content":
                response_parts.append(chunk["content"])
        
        stream_time = time.time() - start_time
        
        # Performance assertions
        assert stream_time < 1.0, f"Streaming response too slow: {stream_time:.2f}s"
        assert len(response_parts) > 0, "No streaming content received"

@pytest.mark.asyncio
async def test_rate_limiting_performance():
    """Test rate limiting implementation performance"""
    
    await cache_service.connect()
    
    if not cache_service.enabled:
        pytest.skip("Redis not available")
    
    user_id = 999
    
    # Test rapid rate limit checks
    start_time = time.time()
    
    for i in range(10):
        count = await cache_service.increment_rate_limit(user_id, 900)
        assert count == i + 1
    
    rate_limit_time = time.time() - start_time
    
    # Performance assertion
    assert rate_limit_time < 0.5, f"Rate limiting too slow: {rate_limit_time:.2f}s"
    
    # Test getting rate limit count
    start_time = time.time()
    
    for i in range(10):
        count = await cache_service.get_rate_limit_count(user_id)
        assert count == 10
    
    get_limit_time = time.time() - start_time
    
    assert get_limit_time < 0.2, f"Rate limit retrieval too slow: {get_limit_time:.2f}s"

def test_concurrent_requests(client):
    """Test API performance under concurrent load"""
    
    import threading
    import time
    
    results = []
    
    def make_request():
        start = time.time()
        response = client.get("/health")
        duration = time.time() - start
        results.append({
            "status_code": response.status_code,
            "duration": duration
        })
    
    # Create 20 concurrent requests
    threads = []
    
    start_time = time.time()
    
    for i in range(20):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    # Performance assertions
    assert len(results) == 20, "Not all requests completed"
    assert all(r["status_code"] == 200 for r in results), "Some requests failed"
    assert total_time < 2.0, f"Concurrent requests too slow: {total_time:.2f}s"
    
    avg_response_time = sum(r["duration"] for r in results) / len(results)
    assert avg_response_time < 0.1, f"Average response time too slow: {avg_response_time:.3f}s"

@pytest.mark.skip("Requires running Redis and WebSocket server")
async def test_websocket_connection_performance():
    """Test WebSocket connection establishment and messaging performance"""
    
    uri = "ws://localhost:8000/api/v1/chat/ws/1"
    
    try:
        # Test connection time
        start_time = time.time()
        
        async with websockets.connect(uri) as websocket:
            connection_time = time.time() - start_time
            
            assert connection_time < 1.0, f"WebSocket connection too slow: {connection_time:.2f}s"
            
            # Test message exchange performance
            test_message = {
                "type": "chat_message",
                "message": "Test message",
                "timestamp": time.time()
            }
            
            start_time = time.time()
            await websocket.send(json.dumps(test_message))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            message_time = time.time() - start_time
            
            assert message_time < 2.0, f"WebSocket message exchange too slow: {message_time:.2f}s"
            
            response_data = json.loads(response)
            assert "type" in response_data
    
    except Exception as e:
        pytest.skip(f"WebSocket server not available: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])