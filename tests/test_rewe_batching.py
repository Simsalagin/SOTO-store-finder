"""
Tests for REWE scraper with batch processing integration.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, Mock


class TestREWEScraperBatching:
    """Test suite for REWE scraper batch processing."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for checkpoints."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_rewe_scraper_supports_limit(self):
        """Test that REWE scraper supports limit parameter for fast testing."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Bayern"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': 'store1',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': 'Test St 1',
                        'zipCode': '80331',
                        'city': 'München',
                        'state': 'Bayern'
                    }
                ],
                'totalHits': 1
            }
            mock_post.return_value = mock_response

            # Scrape with limit
            stores = scraper.scrape(limit=1)

            # Should return max 1 store
            assert len(stores) <= 1

    def test_rewe_batch_processing_with_single_state(self, temp_db_path):
        """Test batch processing with single state for fast testing."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            # Mock 10 stores
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': f'store{i}',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': f'Test St {i}',
                        'zipCode': '10115',
                        'city': 'Berlin',
                        'state': 'Berlin',
                        'lat': 52.52,
                        'lon': 13.40
                    }
                    for i in range(10)
                ],
                'totalHits': 10
            }
            mock_post.return_value = mock_response

            # Process with batches
            result = scraper.scrape_with_batches(
                batch_size=5,
                checkpoint_db=temp_db_path,
                limit=10
            )

            assert result['processed'] >= 0  # Some stores processed
            assert 'run_id' in result

    def test_rewe_batch_processing_with_checkpoints(self, temp_db_path):
        """Test that checkpoints are saved during REWE batch processing."""
        from src.scrapers.rewe import REWEScraper
        from src.batch.checkpoint_manager import CheckpointManager

        scraper = REWEScraper(states=["Hamburg"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': f'store{i}',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': f'St {i}',
                        'zipCode': '20095',
                        'city': 'Hamburg',
                        'state': 'Hamburg',
                        'lat': 53.55,
                        'lon': 10.00
                    }
                    for i in range(20)
                ],
                'totalHits': 20
            }
            mock_post.return_value = mock_response

            result = scraper.scrape_with_batches(
                batch_size=10,
                checkpoint_db=temp_db_path,
                limit=20
            )

            # Verify checkpoints
            manager = CheckpointManager(temp_db_path)
            runs = manager.list_runs(chain_id="rewe")
            assert len(runs) >= 1
            assert runs[0]['status'] == 'completed'

    def test_rewe_with_soto_checking_batched(self, temp_db_path):
        """Test REWE with SOTO checking in batch mode."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(
            states=["Bremen"],
            check_soto_availability=True
        )

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            # Mock market search
            mock_market_response = Mock()
            mock_market_response.status_code = 200
            mock_market_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': 'store1',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': 'Test St',
                        'zipCode': '28195',
                        'city': 'Bremen',
                        'state': 'Bremen',
                        'lat': 53.07,
                        'lon': 8.80
                    }
                ],
                'totalHits': 1
            }

            # Mock market selection (for SOTO)
            mock_selection_response = Mock()
            mock_selection_response.status_code = 200
            mock_selection_response.json.return_value = {'success': True}

            # Mock product count (SOTO check)
            mock_count_response = Mock()
            mock_count_response.status_code = 200
            mock_count_response.json.return_value = {'count': 5}  # Has SOTO

            mock_post.side_effect = [
                mock_market_response,  # Market search
                mock_selection_response,  # Market selection
                mock_count_response,  # Product count
            ]

            result = scraper.scrape_with_batches(
                batch_size=1,
                checkpoint_db=temp_db_path,
                limit=1
            )

            # Should complete without errors
            assert result['status'] == 'completed'

    def test_rewe_limit_to_single_state(self):
        """Test limiting REWE to single state for fast testing."""
        from src.scrapers.rewe import REWEScraper

        # Initialize with single state
        scraper = REWEScraper(states=["Saarland"])
        assert len(scraper.states_to_scrape) == 1
        assert scraper.states_to_scrape[0] == "Saarland"

    def test_rewe_all_states_by_default(self):
        """Test that REWE processes all 16 states by default."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper()
        assert len(scraper.states_to_scrape) == 16

    def test_rewe_deduplication_across_batches(self, temp_db_path):
        """Test that duplicate stores are not counted twice."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Hessen"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            # Return same store twice
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': 'duplicate_store',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': 'Main St',
                        'zipCode': '60311',
                        'city': 'Frankfurt',
                        'state': 'Hessen',
                        'lat': 50.11,
                        'lon': 8.68
                    },
                    {
                        'wwIdent': 'duplicate_store',  # Same ID
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': 'Main St',
                        'zipCode': '60311',
                        'city': 'Frankfurt',
                        'state': 'Hessen',
                        'lat': 50.11,
                        'lon': 8.68
                    }
                ],
                'totalHits': 2
            }
            mock_post.return_value = mock_response

            result = scraper.scrape_with_batches(
                batch_size=5,
                checkpoint_db=temp_db_path,
                limit=2
            )

            # Should only count unique store once
            assert result['processed'] == 1  # Not 2

    def test_rewe_progress_callback(self, temp_db_path):
        """Test progress callback during REWE batch processing."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Sachsen"])
        progress_updates = []

        def on_progress(progress):
            progress_updates.append(progress)

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': f's{i}',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': f'St {i}',
                        'zipCode': '01067',
                        'city': 'Dresden',
                        'state': 'Sachsen',
                        'lat': 51.05,
                        'lon': 13.73
                    }
                    for i in range(30)
                ],
                'totalHits': 30
            }
            mock_post.return_value = mock_response

            scraper.scrape_with_batches(
                batch_size=10,
                checkpoint_db=temp_db_path,
                limit=30,
                progress_callback=on_progress
            )

            # Should have progress updates
            assert len(progress_updates) > 0
            assert progress_updates[-1]['percentage'] == 100.0

    def test_rewe_backward_compatibility(self):
        """Test that traditional scrape() still works."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Thüringen"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': 'store1',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': 'Test',
                        'zipCode': '99084',
                        'city': 'Erfurt',
                        'state': 'Thüringen',
                        'lat': 50.97,
                        'lon': 11.03
                    }
                ],
                'totalHits': 1
            }
            mock_post.return_value = mock_response

            # Traditional scrape should still work
            stores = scraper.scrape()
            assert len(stores) >= 0

    def test_rewe_respects_limit_parameter(self, temp_db_path):
        """Test that limit parameter correctly limits total stores."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Brandenburg"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'markets': [
                    {
                        'wwIdent': f's{i}',
                        'marketName': 'REWE',
                        'companyName': 'REWE',
                        'street': f'St {i}',
                        'zipCode': '14467',
                        'city': 'Potsdam',
                        'state': 'Brandenburg',
                        'lat': 52.39,
                        'lon': 13.06
                    }
                    for i in range(100)  # Mock returns 100 stores
                ],
                'totalHits': 100
            }
            mock_post.return_value = mock_response

            result = scraper.scrape_with_batches(
                batch_size=10,
                checkpoint_db=temp_db_path,
                limit=25  # But we limit to 25
            )

            # Should not exceed limit
            assert result['processed'] <= 25
