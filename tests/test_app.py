import os
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    """Test the health check endpoint"""
    rv = client.get('/health')
    assert rv.status_code == 200
    assert b'healthy' in rv.data

def test_data_directory_exists():
    """Test that the data directory is properly configured"""
    from config import config
    assert os.path.exists(str(config.data_dir))
    assert os.path.exists(str(config.data_dir / 'db'))
    assert os.path.exists(str(config.data_dir / 'config'))
    assert os.path.exists(str(config.data_dir / 'charts'))
    assert os.path.exists(str(config.data_dir / 'logs'))
    assert os.path.exists(str(config.data_dir / 'archive'))